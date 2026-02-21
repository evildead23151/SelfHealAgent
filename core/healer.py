"""
core/healer.py
Auto-heal orchestrator — decides which action to take based on wifi_state
and delegates to the active driver.

All healing actions are wrapped with ArmorIQ intent verification:
  capture_plan → get_intent_token → execute → Merkle verify → audit log
"""

from network.base import NetworkDriver, ping_host
from core import alerts
from core.intent_verification import verify_and_execute
from config.settings import log


def auto_heal(driver: NetworkDriver) -> dict:
    """
    Main healing entry point.
    Returns a JSON-serializable dict with the action taken, outcome,
    and ArmorIQ intent verification details.
    """
    state = driver.get_wifi_state()
    log.info(f"Auto-heal triggered. Current state: {state}")

    # ── No WLAN hardware ─────────────────────────────────────────────────────
    if state == "no_wlan":
        alerts.push("warning", "No Wireless Hardware",
                     "No WLAN adapter found on this system.", state)
        return {"wifi_state": state, "action": "none", "reason": "No wireless hardware"}

    # ── WiFi is OFF — re-enable it ───────────────────────────────────────────
    if state == "wifi_disabled":
        adapter = driver.get_adapter_name()
        alerts.push("critical", "WiFi Disabled",
                     f"WiFi adapter '{adapter}' is turned off. Attempting to re-enable.", state)

        # Wrap with ArmorIQ intent verification
        verified_result = verify_and_execute(
            action_name="enable_wifi",
            action_description=f"Re-enable WiFi adapter '{adapter}' via multi-strategy fallback",
            action_params={"adapter": adapter, "state": state},
            execute_fn=lambda: driver.enable_wifi(),
        )

        result = verified_result["action_result"]
        fixed = result.get("final_state") in ("wifi_connected", "wifi_up_no_net")

        if fixed:
            alerts.push("resolved", "WiFi Restored",
                         f"WiFi adapter '{adapter}' is back online.", result["final_state"])
        else:
            alerts.push("critical", "WiFi Fix Failed",
                         "Could not re-enable WiFi automatically. Manual action required.", state)

        alerts.last_state = state
        return {
            "wifi_state":           state,
            "action":               "enable_wifi",
            "adapter":              adapter,
            "result":               result,
            "fixed":                fixed,
            "intent_verification":  verified_result["intent_verification"],
        }

    # ── WiFi up but no internet ───────────────────────────────────────────────
    if state == "wifi_up_no_net":
        adapter = driver.get_adapter_name()
        alerts.push("warning", "No Internet Access",
                     "WiFi connected but no internet. Restarting network stack.", state)

        verified_result = verify_and_execute(
            action_name="restart_network",
            action_description=f"Restart network stack on adapter '{adapter}' (disable→enable→flush→renew)",
            action_params={"adapter": adapter, "state": state},
            execute_fn=lambda: driver.restart_network(),
        )

        result = verified_result["action_result"]
        fixed = result.get("internet", False)

        if fixed:
            alerts.push("resolved", "Internet Restored",
                         "Network stack restarted. Internet is back.", "wifi_connected")
        else:
            alerts.push("critical", "Network Fix Failed",
                         "Could not restore internet automatically.", state)

        alerts.last_state = state
        return {
            "wifi_state":           state,
            "action":               "restart_network",
            "adapter":              adapter,
            "result":               result,
            "fixed":                fixed,
            "intent_verification":  verified_result["intent_verification"],
        }

    # ── Seems healthy — double-check with a live ping ─────────────────────────
    if ping_host(count=2, timeout_ms=2000):
        prev = getattr(alerts, "last_state", "unknown")
        if prev in ("wifi_disabled", "wifi_up_no_net"):
            alerts.push("resolved", "Connection Healthy",
                         "All systems are operating normally.", state)
        alerts.last_state = state
        return {"wifi_state": state, "action": "none", "reason": "Everything looks fine"}

    # ── Minor blip — flush DNS only ───────────────────────────────────────────
    verified_result = verify_and_execute(
        action_name="flush_dns",
        action_description="Flush OS DNS cache to resolve intermittent connectivity",
        action_params={"state": state},
        execute_fn=lambda: {"ok": driver.flush_dns()[0], "output": driver.flush_dns()[1]},
    )

    alerts.push("info", "DNS Flushed",
                 "Connectivity issue detected. DNS cache cleared.", state)
    alerts.last_state = state
    return {
        "wifi_state":           state,
        "action":               "flush_dns_only",
        "flush_ok":             verified_result["action_result"].get("ok", False),
        "intent_verification":  verified_result["intent_verification"],
    }
