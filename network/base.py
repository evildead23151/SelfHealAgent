"""
network/base.py
Abstract base class (interface) for platform-specific network drivers,
plus shared cross-platform helpers (ping, DNS, process runner).
"""

import subprocess
import sys
from abc import ABC, abstractmethod

# Use Windows-specific DETACHED_PROCESS flag only on Windows
_CREATE_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


# ── Shared helpers ─────────────────────────────────────────────────────────────

def run_cmd(cmd: list, timeout: int = 15) -> tuple[bool, str]:
    """Run a subprocess command and return (success, combined_output)."""
    try:
        kwargs = dict(capture_output=True, text=True, timeout=timeout)
        if sys.platform.startswith("win"):
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        r = subprocess.run(cmd, **kwargs)
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def ping_host(host: str = "8.8.8.8", count: int = 1, timeout_ms: int = 2000) -> bool:
    """Ping a host. Returns True if reachable."""
    if sys.platform.startswith("win"):
        ok, _ = run_cmd(["ping", "-n", str(count), "-w", str(timeout_ms), host])
    else:
        ok, _ = run_cmd(["ping", "-c", str(count), "-W", str(timeout_ms // 1000 or 1), host])
    return ok


def resolve_dns(host: str = "google.com") -> bool:
    """Try nslookup. Returns True if resolution succeeds."""
    ok, _ = run_cmd(["nslookup", host])
    return ok


# ── Abstract driver ────────────────────────────────────────────────────────────

class NetworkDriver(ABC):
    """Platform-specific implementation contract."""

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the primary wireless adapter name."""

    @abstractmethod
    def get_wifi_state(self) -> str:
        """
        Return one of:
          'wifi_connected'  – connected and internet reachable
          'wifi_up_no_net'  – adapter up but no internet
          'wifi_disabled'   – adapter/radio is off
          'no_wlan'         – no WLAN hardware
        """

    @abstractmethod
    def enable_wifi(self) -> dict:
        """Attempt to re-enable the WiFi radio/adapter."""

    @abstractmethod
    def restart_network(self) -> dict:
        """Restart the network stack (disable → enable → flush DNS → renew IP)."""

    @abstractmethod
    def flush_dns(self) -> tuple[bool, str]:
        """Flush the OS DNS cache."""
