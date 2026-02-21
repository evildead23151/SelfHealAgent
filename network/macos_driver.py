"""
network/macos_driver.py
macOS-specific NetworkDriver implementation.

Uses:
  - networksetup   for WiFi state + enable/disable
  - ifconfig       as a reliable fallback for connection status
  - dscacheutil    for DNS flush
"""

import time

from network.base import NetworkDriver, run_cmd, ping_host, resolve_dns
from config.settings import log


class MacOSDriver(NetworkDriver):

    def get_adapter_name(self) -> str:
        """Return the primary WiFi interface name (usually 'en0')."""
        ok, out = run_cmd(["networksetup", "-listallhardwareports"])
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if "wi-fi" in line.lower() or "airport" in line.lower() or "wireless" in line.lower():
                # Next line(s) will have 'Device: enX'
                for j in range(i + 1, min(i + 4, len(lines))):
                    if "device:" in lines[j].lower():
                        return lines[j].split(":", 1)[1].strip()
        return "en0"

    def get_wifi_state(self) -> str:
        adapter = self.get_adapter_name()

        # Check hardware power first
        ok_pwr, out_pwr = run_cmd(["networksetup", "-getairportpower", adapter])
        if ok_pwr and "Off" in out_pwr:
            return "wifi_disabled"

        # Check ifconfig status (more reliable on modern macOS)
        ok_ifc, out_ifc = run_cmd(["ifconfig", adapter])
        if ok_ifc:
            has_inet = any("inet " in l for l in out_ifc.splitlines())
            status_up = "status: active" in out_ifc.lower() or "flags=" in out_ifc
            if not has_inet or not status_up:
                return "wifi_disabled"
        else:
            return "wifi_disabled"

        return "wifi_connected" if ping_host() else "wifi_up_no_net"

    def enable_wifi(self) -> dict:
        adapter = self.get_adapter_name()
        steps = []
        ok1, out1 = run_cmd(["networksetup", "-setairportpower", adapter, "on"])
        steps.append({"step": "setairportpower-on", "ok": ok1, "out": out1})
        log.info(f"networksetup -setairportpower on: ok={ok1} | {out1}")
        time.sleep(5)
        state = self.get_wifi_state()
        steps.append({"step": "verify", "state": state})
        return {"steps": steps, "final_state": state}

    def restart_network(self) -> dict:
        adapter = self.get_adapter_name()
        steps = []

        ok1, _ = run_cmd(["networksetup", "-setairportpower", adapter, "off"])
        steps.append({"step": "disable", "ok": ok1})
        time.sleep(3)

        ok2, _ = run_cmd(["networksetup", "-setairportpower", adapter, "on"])
        steps.append({"step": "enable", "ok": ok2})
        time.sleep(5)

        ok3, _ = self.flush_dns()
        steps.append({"step": "flush_dns", "ok": ok3})

        # Renew DHCP lease
        ok4, _ = run_cmd(["ipconfig", "set", adapter, "DHCP"])
        steps.append({"step": "renew_dhcp", "ok": ok4})
        time.sleep(3)

        ok5 = ping_host()
        steps.append({"step": "ping_check", "ok": ok5})
        return {"steps": steps, "internet": ok5}

    def flush_dns(self) -> tuple[bool, str]:
        # Try dscacheutil first, then mDNSResponder restart
        ok1, out1 = run_cmd(["dscacheutil", "-flushcache"])
        run_cmd(["killall", "-HUP", "mDNSResponder"])
        return ok1, out1
