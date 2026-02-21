"""
network/windows_driver.py
Windows-specific NetworkDriver implementation.

WiFi enable uses a 4-strategy fallback chain:
  1. WinRT Radio API   — toggles the SOFTWARE radio kill switch (taskbar toggle)
  2. PnP Radio device  — Enable the SWD\\RADIO PnP device
  3. Enable-NetAdapter — PowerShell adapter enable
  4. PnP Wireless blast— Enable all wireless PnP devices (broad fallback)

The WinRT strategy is the ONLY one that reliably handles the Windows
software radio kill switch. Enable-NetAdapter touches the adapter,
not the radio — so it returns ok=True but WiFi stays off.

IMPORTANT: winrt must be installed to the same Python that runs this agent:
    python -m pip install winrt-runtime "winrt-Windows.Devices.Radios"
"""

import time

from network.base import NetworkDriver, run_cmd, ping_host, resolve_dns
from config.settings import log


# ── PowerShell helper ──────────────────────────────────────────────────────────

def _ps(script: str, timeout: int = 20):
    return run_cmd(
        ["powershell", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


class WindowsDriver(NetworkDriver):

    def __init__(self):
        self._adapter: str = self._detect_adapter()
        self._radio_instance_id: str | None = None

    # ── Adapter detection ──────────────────────────────────────────────────────

    def _detect_adapter(self) -> str:
        ok, out = _ps(
            "Get-NetAdapter | Where-Object {"
            "$_.InterfaceDescription -like '*Wireless*' "
            "-or $_.Name -like '*Wi-Fi*' "
            "-or $_.Name -like '*WLAN*'"
            "} | Select-Object -ExpandProperty Name"
        )
        if ok and out.strip():
            return out.strip().splitlines()[0].strip()
        ok2, out2 = run_cmd(["netsh", "wlan", "show", "interfaces"])
        if ok2:
            for line in out2.splitlines():
                if "Name" in line and ":" in line:
                    return line.split(":", 1)[1].strip()
        return "Wi-Fi"

    def get_adapter_name(self) -> str:
        return self._adapter

    # ── SWD\\RADIO PnP discovery ───────────────────────────────────────────────

    def _get_radio_instance_id(self) -> str | None:
        if self._radio_instance_id:
            return self._radio_instance_id
        ok, out = _ps(
            "Get-PnpDevice | Where-Object {"
            "$_.FriendlyName -eq 'Wi-Fi' -and "
            "$_.InstanceId -like 'SWD\\\\RADIO\\\\*'"
            "} | Select-Object -ExpandProperty InstanceId"
        )
        if ok and out.strip():
            self._radio_instance_id = out.strip().splitlines()[0].strip()
            log.info(f"Radio PnP InstanceId: {self._radio_instance_id}")
        return self._radio_instance_id

    # ── WiFi state detection ───────────────────────────────────────────────────

    def get_wifi_state(self) -> str:
        # 1. Check adapter status via PowerShell
        ok, out = _ps(
            f'(Get-NetAdapter -Name "{self._adapter}" '
            f'-ErrorAction SilentlyContinue).Status'
        )
        status = out.strip().lower()

        if not ok or "disabled" in status or status in ("", "notpresent"):
            # Adapter-level check suggests disabled — verify via netsh
            ok2, out2 = run_cmd(["netsh", "wlan", "show", "interfaces"])
            if "there is no wireless interface" in out2.lower() or not ok2:
                return "wifi_disabled"
            for line in out2.splitlines():
                if "state" in line.lower() and ":" in line:
                    val = line.split(":", 1)[1].strip().lower()
                    if val in ("disconnected", "disconnecting", "not connected"):
                        return "wifi_disabled"
            return "wifi_disabled"

        # Adapter is up — check if WLAN is actually connected
        ok3, out3 = run_cmd(["netsh", "wlan", "show", "interfaces"])
        if "there is no wireless interface" in out3.lower():
            return "no_wlan"

        connected = False
        for line in out3.splitlines():
            if "ssid" in line.lower() and "bssid" not in line.lower() and ":" in line:
                if line.split(":", 1)[1].strip():
                    connected = True
                    break
            if "state" in line.lower() and ":" in line:
                if line.split(":", 1)[1].strip().lower() == "connected":
                    connected = True

        if not connected:
            return "wifi_disabled"

        return "wifi_connected" if ping_host() else "wifi_up_no_net"

    # ── WiFi enable strategies ─────────────────────────────────────────────────

    def _strategy_winrt_radio(self) -> tuple[bool, str]:
        """
        PRIMARY: WinRT Radio API.
        The ONLY reliable way to toggle the Windows software radio kill switch.

        NOTE: asyncio.new_event_loop() works in a background thread on Windows.
        winrt uses asyncio internally via its own COM STA integration.
        """
        try:
            import asyncio
            from winrt.windows.devices.radios import Radio, RadioState, RadioKind

            async def _turn_on():
                radios = await Radio.get_radios_async()
                for r in radios:
                    if r.kind == RadioKind.WI_FI:
                        result = await r.set_state_async(RadioState.ON)
                        return True, f"set_state result: {result}"
                return False, "No WiFi radio found in WinRT enumeration"

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ok, msg = loop.run_until_complete(_turn_on())
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            return ok, msg

        except ImportError:
            return False, (
                'winrt not installed — run: '
                'python -m pip install winrt-runtime "winrt-Windows.Devices.Radios"'
            )
        except Exception as e:
            return False, str(e)

    def _strategy_pnpdevice_radio(self) -> tuple[bool, str]:
        """FALLBACK 2: Enable the SWD\\RADIO PnP device."""
        instance_id = self._get_radio_instance_id()
        if not instance_id:
            return False, "SWD\\RADIO PnP device not found"
        ok, out = _ps(
            f'Get-PnpDevice -InstanceId "{instance_id}" | Enable-PnpDevice -Confirm:$false'
        )
        return ok, out

    def _strategy_enable_netadapter(self) -> tuple[bool, str]:
        """FALLBACK 3: PowerShell Enable-NetAdapter."""
        ok, out = _ps(f'Enable-NetAdapter -Name "{self._adapter}" -Confirm:$false')
        return ok, out

    def _strategy_pnpdevice_wireless(self) -> tuple[bool, str]:
        """FALLBACK 4: Enable all wireless PnP devices."""
        ok, out = _ps(
            "Get-PnpDevice | Where-Object {"
            "$_.FriendlyName -like '*Wi-Fi*' "
            "-or $_.FriendlyName -like '*Wireless*'"
            "} | Enable-PnpDevice -Confirm:$false"
        )
        return ok, out

    # ── enable_wifi orchestrator ────────────────────────────────────────────────

    def enable_wifi(self) -> dict:
        """Try each strategy in sequence; stop early if WiFi comes back."""
        steps = []
        strategies = [
            ("winrt-radio-api",    self._strategy_winrt_radio),
            ("pnpdevice-radio",    self._strategy_pnpdevice_radio),
            ("Enable-NetAdapter",  self._strategy_enable_netadapter),
            ("pnpdevice-wireless", self._strategy_pnpdevice_wireless),
        ]

        for name, strategy in strategies:
            ok, out = strategy()
            steps.append({"step": name, "ok": ok, "out": out})
            log.info(f"WiFi enable [{name}]: ok={ok} | {out}")

            if ok:
                # Ensure WLAN service is running
                _ps(
                    "Set-Service -Name WlanSvc -StartupType Automatic; "
                    "Start-Service -Name WlanSvc -ErrorAction SilentlyContinue"
                )
                time.sleep(5)
                state = self.get_wifi_state()
                if state in ("wifi_connected", "wifi_up_no_net"):
                    steps.append({"step": "verify", "state": state})
                    return {"steps": steps, "final_state": state}
                # Strategy returned ok but WiFi still off — try next

        # All strategies exhausted
        _ps(
            "Set-Service -Name WlanSvc -StartupType Automatic; "
            "Start-Service -Name WlanSvc -ErrorAction SilentlyContinue"
        )
        time.sleep(5)
        final = self.get_wifi_state()
        steps.append({"step": "verify", "state": final})
        return {"steps": steps, "final_state": final}

    # ── Network restart ─────────────────────────────────────────────────────────

    def restart_network(self) -> dict:
        steps = []
        ok1, _ = _ps(f'Disable-NetAdapter -Name "{self._adapter}" -Confirm:$false')
        steps.append({"step": "disable", "ok": ok1})
        time.sleep(3)
        ok2, _ = _ps(f'Enable-NetAdapter -Name "{self._adapter}" -Confirm:$false')
        steps.append({"step": "enable", "ok": ok2})
        time.sleep(5)
        ok3, _ = self.flush_dns()
        steps.append({"step": "flush_dns", "ok": ok3})
        run_cmd(["ipconfig", "/release"])
        time.sleep(2)
        ok4, _ = run_cmd(["ipconfig", "/renew"])
        steps.append({"step": "renew_ip", "ok": ok4})
        time.sleep(3)
        ok5 = ping_host()
        steps.append({"step": "ping_check", "ok": ok5})
        return {"steps": steps, "internet": ok5}

    def flush_dns(self) -> tuple[bool, str]:
        return run_cmd(["ipconfig", "/flushdns"])
