"""
network/cloud_driver.py
Cloud/demo NetworkDriver implementation.

Used when running on Linux (Render, Docker, etc.) where there is no real
WiFi hardware. Provides deterministic simulation for demo purposes.

State can be forced via `force_state()` for the /simulate-wifi-failure endpoint.
"""

import time
import threading

from network.base import NetworkDriver, ping_host, resolve_dns
from config.settings import log


class CloudDriver(NetworkDriver):
    """Simulated network driver for cloud/demo deployments."""

    _lock = threading.Lock()

    def __init__(self):
        self._adapter = "cloud-vnet0"
        self._forced_state: str | None = None
        self._forced_until: float = 0
        self._heal_count = 0

    # ── Public API to force failures ──────────────────────────────────────────

    def force_state(self, state: str, duration_seconds: float = 15.0) -> None:
        """Force a specific WiFi state for `duration_seconds`."""
        with self._lock:
            self._forced_state = state
            self._forced_until = time.time() + duration_seconds
        log.info(f"[CloudDriver] Forced state='{state}' for {duration_seconds}s")

    def clear_forced_state(self) -> None:
        with self._lock:
            self._forced_state = None
            self._forced_until = 0

    # ── NetworkDriver interface ───────────────────────────────────────────────

    def get_adapter_name(self) -> str:
        return self._adapter

    def get_wifi_state(self) -> str:
        with self._lock:
            if self._forced_state and time.time() < self._forced_until:
                return self._forced_state
            elif self._forced_state and time.time() >= self._forced_until:
                self._forced_state = None
        # On cloud, try real ping; if unavailable, report connected
        try:
            if ping_host(timeout_ms=2000):
                return "wifi_connected"
            if resolve_dns():
                return "wifi_up_no_net"
            return "wifi_connected"  # cloud usually has internet
        except Exception:
            return "wifi_connected"

    def enable_wifi(self) -> dict:
        self._heal_count += 1
        log.info(f"[CloudDriver] Simulating WiFi enable (heal #{self._heal_count})")
        steps = [
            {"step": "cloud-radio-api", "ok": True, "out": "Simulated WinRT radio toggle"},
        ]
        # Clear forced state after "healing"
        time.sleep(1)
        self.clear_forced_state()
        state = self.get_wifi_state()
        steps.append({"step": "verify", "state": state})
        return {"steps": steps, "final_state": state}

    def restart_network(self) -> dict:
        self._heal_count += 1
        log.info(f"[CloudDriver] Simulating network restart (heal #{self._heal_count})")
        steps = [
            {"step": "disable",     "ok": True},
            {"step": "enable",      "ok": True},
            {"step": "flush_dns",   "ok": True},
            {"step": "renew_ip",    "ok": True},
            {"step": "ping_check",  "ok": True},
        ]
        time.sleep(1)
        self.clear_forced_state()
        return {"steps": steps, "internet": True}

    def flush_dns(self) -> tuple[bool, str]:
        log.info("[CloudDriver] Simulating DNS flush")
        return True, "DNS cache flushed (simulated)"
