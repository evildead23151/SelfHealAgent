"""
core/simulator.py
Deterministic failure simulation for hackathon demos.

Provides:
  - simulate_wifi_failure(driver)  → forces wifi_disabled, auto-heals, logs
  - unsafe_action_attempt()        → attempts action without token, gets blocked
  - demo_mode_loop(driver)         → background thread, random failures every 60-120s
"""

import time
import random
import threading

from config.settings import log, DEMO_MODE
from core import alerts
from core.intent_verification import log_blocked_action, verify_and_execute


def simulate_wifi_failure(driver) -> dict:
    """
    POST /simulate-wifi-failure handler logic.
    1. Force WiFi state to 'wifi_disabled'
    2. Push a critical alert
    3. Run auto-heal with full intent verification
    4. Return the complete simulation report
    """
    log.info("[Simulator] WiFi failure simulation triggered")

    # Force the driver into disabled state
    if hasattr(driver, "force_state"):
        driver.force_state("wifi_disabled", duration_seconds=12.0)
    else:
        log.warning("[Simulator] Driver does not support force_state; simulating in-memory only")

    # Push alerts
    adapter = driver.get_adapter_name()
    alerts.push("critical", "⚡ Simulated WiFi Failure",
                f"WiFi adapter '{adapter}' forced offline for demo. Auto-healing initiated.", "wifi_disabled")

    # Run auto-heal with full ArmorIQ verification
    verified_result = verify_and_execute(
        action_name="enable_wifi",
        action_description=f"[DEMO] Re-enable WiFi adapter '{adapter}' after simulated failure",
        action_params={"adapter": adapter, "state": "wifi_disabled", "simulated": True},
        execute_fn=lambda: driver.enable_wifi(),
    )

    result = verified_result["action_result"]
    fixed = result.get("final_state") in ("wifi_connected", "wifi_up_no_net")

    if fixed:
        alerts.push("resolved", "✅ WiFi Restored (Demo)",
                     f"WiFi adapter '{adapter}' recovered after simulated failure.", result.get("final_state", "wifi_connected"))
    else:
        alerts.push("warning", "Healing In Progress",
                     f"WiFi adapter '{adapter}' is being restored.", "wifi_disabled")

    log.info(f"[Simulator] Simulation complete: fixed={fixed}")

    return {
        "simulation": True,
        "wifi_state_before": "wifi_disabled",
        "wifi_state_after": result.get("final_state", "unknown"),
        "action": "enable_wifi",
        "adapter": adapter,
        "fixed": fixed,
        "result": result,
        "intent_verification": verified_result["intent_verification"],
    }


def unsafe_action_attempt() -> dict:
    """
    POST /unsafe-action handler logic.
    Attempts to execute a system action WITHOUT an intent token.
    ArmorIQ blocks the action and logs the security event.
    """
    action_name = "escalate_privileges"
    reason = "No intent token provided. Action was not declared in any execution plan. " \
             "ArmorIQ requires cryptographic verification before system actions can execute."

    log.warning(f"[Security] BLOCKED unsafe action: {action_name}")

    # Log the blocked action in intent verification
    blocked_entry = log_blocked_action(action_name, reason)

    # Push a security alert
    alerts.push("critical", "🛡️ Action Blocked by ArmorIQ",
                f"Attempted '{action_name}' without intent verification. Action denied.",
                "security_block")

    return {
        "status": "blocked",
        "action": action_name,
        "reason": reason,
        "security": {
            "intent_token": None,
            "plan_hash": None,
            "merkle_proof": None,
            "verification": "FAILED — no token provided",
        },
        "recommendation": "Use client.capture_plan() → client.get_intent_token() → client.invoke() flow",
        "blocked_entry": blocked_entry,
    }


def _demo_loop(driver) -> None:
    """Background loop for VOLTIX_DEMO_MODE: auto-generates failures."""
    time.sleep(15)  # Wait for server startup
    log.info("[DemoMode] Auto-failure generation started (60-120s interval)")

    failure_types = [
        ("wifi_disabled", "WiFi adapter offline"),
        ("wifi_up_no_net", "WiFi connected but no internet"),
    ]

    cycle = 0
    while True:
        try:
            cycle += 1
            wait = random.randint(60, 120)
            log.info(f"[DemoMode] Next failure in {wait}s (cycle #{cycle})")
            time.sleep(wait)

            # Alternate between failure simulation and unsafe action block
            if cycle % 3 == 0:
                # Every 3rd cycle: demonstrate security blocking
                log.info("[DemoMode] Triggering security block demo")
                unsafe_action_attempt()
            else:
                # Normal cycle: simulate wifi failure + auto-heal
                state, desc = random.choice(failure_types)
                log.info(f"[DemoMode] Simulating: {desc}")
                if hasattr(driver, "force_state"):
                    driver.force_state(state, duration_seconds=12.0)

                adapter = driver.get_adapter_name()
                alerts.push("critical" if state == "wifi_disabled" else "warning",
                            f"⚡ Demo: {desc}",
                            f"Auto-generated failure on '{adapter}' (demo mode cycle #{cycle})",
                            state)

                verified_result = verify_and_execute(
                    action_name="enable_wifi" if state == "wifi_disabled" else "restart_network",
                    action_description=f"[DEMO] Auto-heal: {desc}",
                    action_params={"adapter": adapter, "state": state, "demo_cycle": cycle},
                    execute_fn=lambda: driver.enable_wifi() if state == "wifi_disabled" else driver.restart_network(),
                )

                result = verified_result["action_result"]
                fixed = result.get("final_state", "") in ("wifi_connected", "wifi_up_no_net") or result.get("internet", False)
                if fixed:
                    alerts.push("resolved", "✅ Demo: Auto-Healed",
                                f"System recovered (cycle #{cycle})", "wifi_connected")

        except Exception as e:
            log.error(f"[DemoMode] Error in demo loop: {e}")


def start_demo_mode(driver) -> None:
    """Start the demo-mode background thread if VOLTIX_DEMO_MODE is enabled."""
    if not DEMO_MODE:
        return
    t = threading.Thread(target=_demo_loop, args=(driver,), daemon=True)
    t.start()
    log.info("[DemoMode] Background failure generator ACTIVE")
