"""
core/diagnostics.py
Collects a full system diagnostic snapshot via the active driver.
"""

from network.base import NetworkDriver, ping_host, resolve_dns, run_cmd
from config.settings import VERSION, IS_WINDOWS


def get_diagnostics(driver: NetworkDriver) -> dict:
    adapter = driver.get_adapter_name()
    state   = driver.get_wifi_state()

    ok_ping = ping_host()
    ok_dns  = resolve_dns()

    payload = {
        "version":       VERSION,
        "adapter":       adapter,
        "wifi_state":    state,
        "internet_ping": ok_ping,
        "dns_resolution": ok_dns,
    }

    # Windows extras
    if IS_WINDOWS:
        _, wlan_out = run_cmd(["netsh", "wlan", "show", "interfaces"])
        payload["wlan_interfaces_raw"] = wlan_out[:600]
        from network.windows_driver import _ps
        _, adapter_out = _ps(
            f'Get-NetAdapter -Name "{adapter}" -ErrorAction SilentlyContinue '
            f'| Select-Object Name,Status,LinkSpeed | ConvertTo-Json'
        )
        payload["adapter_info"] = adapter_out[:400]

    return payload
