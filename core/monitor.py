"""
core/monitor.py
Background thread that polls network state every 15 seconds
and pushes alerts when transitions are detected.
"""

import threading
import time

from network.base import NetworkDriver
from core import alerts
from config.settings import log


def _monitor_loop(driver: NetworkDriver) -> None:
    time.sleep(10)  # Wait for server to fully start
    while True:
        try:
            state = driver.get_wifi_state()
            prev  = getattr(alerts, "last_state", "unknown")

            if state != prev:
                log.info(f"[Monitor] State: {prev} → {state}")
                if state == "wifi_disabled":
                    alerts.push("critical", "WiFi Disabled Detected",
                                f"WiFi turned off on adapter '{driver.get_adapter_name()}'.", state)
                elif state == "wifi_up_no_net":
                    alerts.push("warning", "Internet Lost",
                                "WiFi connected but no internet access.", state)
                elif state == "wifi_connected" and prev in ("wifi_disabled", "wifi_up_no_net"):
                    alerts.push("resolved", "Connection Restored",
                                "Network is healthy again.", state)
                alerts.last_state = state

        except Exception as e:
            log.error(f"[Monitor] Unhandled error: {e}")

        time.sleep(15)


def start_monitor(driver: NetworkDriver) -> None:
    """Start the background monitor as a daemon thread."""
    t = threading.Thread(target=_monitor_loop, args=(driver,), daemon=True)
    t.start()
    log.info("Background network monitor started (polls every 15s)")
