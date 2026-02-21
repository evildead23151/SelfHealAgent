r"""
Voltix Mechanic Agent v5.1.0
Autonomous self-healing infrastructure agent - Windows WiFi/Network/DNS
Includes: browser dashboard, real-time alerts, ArmorIQ-compatible API

PREREQUISITE (run once in Admin PowerShell):
    python -m pip install winrt-runtime "winrt-Windows.Devices.Radios"

USAGE (Admin PowerShell):
    $env:VOLTIX_API_KEY="mykey"
    python voltix_mechanic_agent.py

The agent uses a multi-strategy fallback chain to re-enable WiFi:
  1. WinRT Radio API   -- toggles the software radio kill switch (primary)
  2. PnP Radio device  -- enables the SWD\RADIO PnP device
  3. Enable-NetAdapter -- enables the network adapter via PowerShell
  4. PnP Wireless blast -- enables all wireless PnP devices
"""

VERSION = "5.1.0"

import os
import subprocess
import sys
import time
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────
PORT    = int(os.environ.get("VOLTIX_PORT", 3000))
API_KEY = os.environ.get("VOLTIX_API_KEY", "mykey")
LOG_LVL = os.environ.get("VOLTIX_LOG_LEVEL", "INFO")

logging.basicConfig(level=getattr(logging, LOG_LVL),
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("voltix")

# ── In-memory alert store ────────────────────────────────────────────────────
alerts = []
last_state = "unknown"
alert_lock = threading.Lock()

def push_alert(level: str, title: str, message: str, state: str):
    alert = {
        "id": int(time.time() * 1000),
        "level": level,
        "title": title,
        "message": message,
        "state": state,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with alert_lock:
        alerts.insert(0, alert)
        if len(alerts) > 50:
            alerts.pop()
    log.info(f"ALERT [{level.upper()}] {title}: {message}")
    return alert


# ── Shell helpers ────────────────────────────────────────────────────────────
def run(cmd: list, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, creationflags=0x08000000)
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)

def ps(script: str, timeout=20):
    return run(["powershell", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", script], timeout=timeout)


# ── WiFi adapter detection ───────────────────────────────────────────────────
def get_wlan_adapter():
    ok, out = ps("Get-NetAdapter | Where-Object {$_.InterfaceDescription -like '*Wireless*' -or $_.Name -like '*Wi-Fi*' -or $_.Name -like '*WLAN*'} | Select-Object -ExpandProperty Name")
    if ok and out.strip():
        return out.strip().splitlines()[0].strip()
    ok2, out2 = run(["netsh", "wlan", "show", "interfaces"])
    if ok2:
        for line in out2.splitlines():
            if "Name" in line and ":" in line:
                return line.split(":", 1)[1].strip()
    return "Wi-Fi"

ADAPTER = get_wlan_adapter()
log.info(f"Detected WLAN adapter: '{ADAPTER}'")

# Cache for PnP radio instance ID
_radio_instance_id = None

def _get_radio_instance_id():
    """Discover the SWD\\RADIO PnP device ID for the WiFi radio."""
    global _radio_instance_id
    if _radio_instance_id:
        return _radio_instance_id
    ok, out = ps(
        "Get-PnpDevice | Where-Object {"
        "$_.FriendlyName -eq 'Wi-Fi' -and "
        "$_.InstanceId -like 'SWD\\\\RADIO\\\\*'"
        "} | Select-Object -ExpandProperty InstanceId"
    )
    if ok and out.strip():
        _radio_instance_id = out.strip().splitlines()[0].strip()
        log.info(f"Radio PnP InstanceId: {_radio_instance_id}")
    return _radio_instance_id


# ── State detection ──────────────────────────────────────────────────────────
def get_wifi_state():
    ok, out = ps(f'(Get-NetAdapter -Name "{ADAPTER}" -ErrorAction SilentlyContinue).Status')
    status = out.strip().lower()

    if not ok or "disabled" in status or status in ("", "notpresent"):
        ok2, out2 = run(["netsh", "wlan", "show", "interfaces"])
        if "there is no wireless interface" in out2.lower() or not ok2:
            return "wifi_disabled"
        for line in out2.splitlines():
            if "state" in line.lower() and ":" in line:
                val = line.split(":", 1)[1].strip().lower()
                if val in ("disconnected", "disconnecting", "not connected"):
                    return "wifi_disabled"
        return "wifi_disabled"

    ok3, out3 = run(["netsh", "wlan", "show", "interfaces"])
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

    ok4, _ = run(["ping", "-n", "1", "-w", "2000", "8.8.8.8"])
    return "wifi_connected" if ok4 else "wifi_up_no_net"


def flush_dns():
    ok, out = run(["ipconfig", "/flushdns"])
    return ok, out

def renew_ip():
    run(["ipconfig", "/release"])
    time.sleep(2)
    ok, out = run(["ipconfig", "/renew"])
    return ok, out


# ══════════════════════════════════════════════════════════════════════════════
#  WiFi Enable — Multi-strategy fallback chain
# ══════════════════════════════════════════════════════════════════════════════

def _strategy_winrt_radio():
    """
    Strategy 1 (PRIMARY): Toggle WiFi radio via WinRT API.
    This is the ONLY method that reliably handles the Windows software
    radio kill switch (the one toggled from the taskbar).
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
        asyncio.set_event_loop(loop)   # ← required: winrt COM STA integration needs this
        try:
            ok, msg = loop.run_until_complete(_turn_on())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return ok, msg
    except ImportError:
        return False, (
            "winrt not installed — run: "
            'python -m pip install winrt-runtime "winrt-Windows.Devices.Radios"'
        )
    except Exception as e:
        return False, str(e)


def _strategy_pnpdevice_radio():
    """
    Strategy 2 (fallback): Enable the SWD\\RADIO PnP device.
    Works on some hardware but not all.
    """
    instance_id = _get_radio_instance_id()
    if not instance_id:
        return False, "Could not find SWD\\RADIO PnP device"
    ok, out = ps(f'Get-PnpDevice -InstanceId "{instance_id}" | Enable-PnpDevice -Confirm:$false')
    return ok, out


def _strategy_enable_netadapter():
    """
    Strategy 3 (fallback): Enable-NetAdapter.
    Handles adapter-level disabling but NOT the radio kill switch.
    """
    ok, out = ps(f'Enable-NetAdapter -Name "{ADAPTER}" -Confirm:$false')
    return ok, out


def _strategy_pnpdevice_wireless():
    """
    Strategy 4 (fallback): Enable all wireless PnP devices.
    Broad blast that handles some edge cases.
    """
    ok, out = ps(
        "Get-PnpDevice | Where-Object {"
        "$_.FriendlyName -like '*Wi-Fi*' "
        "-or $_.FriendlyName -like '*Wireless*'"
        "} | Enable-PnpDevice -Confirm:$false"
    )
    return ok, out


def enable_wifi():
    """
    Attempt to re-enable WiFi using multiple strategies in order.
    Stops early if any strategy succeeds (verified by state check).
    """
    steps = []

    strategies = [
        ("winrt-radio-api",       _strategy_winrt_radio),
        ("pnpdevice-radio",       _strategy_pnpdevice_radio),
        ("Enable-NetAdapter",     _strategy_enable_netadapter),
        ("pnpdevice-wireless",    _strategy_pnpdevice_wireless),
    ]

    for name, strategy in strategies:
        ok, out = strategy()
        steps.append({"step": name, "ok": ok, "out": out})
        log.info(f"WiFi enable [{name}]: ok={ok} | {out}")

        if ok:
            # Ensure WlanSvc is running after any successful toggle
            ps("Set-Service -Name WlanSvc -StartupType Automatic; "
               "Start-Service -Name WlanSvc -ErrorAction SilentlyContinue")
            time.sleep(5)

            state = get_wifi_state()
            if state in ("wifi_connected", "wifi_up_no_net"):
                steps.append({"step": "verify", "state": state})
                return {"steps": steps, "final_state": state}
            # Strategy reported OK but WiFi still off — try next

    # All strategies exhausted — final verify
    ps("Set-Service -Name WlanSvc -StartupType Automatic; "
       "Start-Service -Name WlanSvc -ErrorAction SilentlyContinue")
    time.sleep(5)
    final = get_wifi_state()
    steps.append({"step": "verify", "state": final})
    return {"steps": steps, "final_state": final}


def restart_network():
    steps = []
    ok1, _ = ps(f'Disable-NetAdapter -Name "{ADAPTER}" -Confirm:$false')
    steps.append({"step": "disable", "ok": ok1})
    time.sleep(3)
    ok2, _ = ps(f'Enable-NetAdapter -Name "{ADAPTER}" -Confirm:$false')
    steps.append({"step": "enable", "ok": ok2})
    time.sleep(5)
    ok3, _ = flush_dns()
    steps.append({"step": "flush_dns", "ok": ok3})
    ok4, _ = renew_ip()
    steps.append({"step": "renew_ip", "ok": ok4})
    time.sleep(3)
    ok5, _ = run(["ping", "-n", "1", "-w", "3000", "8.8.8.8"])
    steps.append({"step": "ping_check", "ok": ok5})
    return {"steps": steps, "internet": ok5}


# ── Auto-heal orchestrator ───────────────────────────────────────────────────
def auto_heal():
    global last_state
    state = get_wifi_state()
    log.info(f"Auto-heal triggered. State: {state}")

    if state == "no_wlan":
        push_alert("warning", "No Wireless Hardware", "No WLAN adapter found on this system.", state)
        return {"wifi_state": state, "action": "none", "reason": "No wireless hardware"}

    if state == "wifi_disabled":
        push_alert("critical", "WiFi Disabled", f"WiFi adapter '{ADAPTER}' is turned off. Attempting to re-enable.", state)
        result = enable_wifi()
        fixed = result["final_state"] in ("wifi_connected", "wifi_up_no_net")
        if fixed:
            push_alert("resolved", "WiFi Restored", f"WiFi adapter '{ADAPTER}' is back online.", result["final_state"])
        else:
            push_alert("critical", "WiFi Fix Failed", "Could not re-enable WiFi automatically. Manual action required.", state)
        last_state = state
        return {"wifi_state": state, "action": "enable_wifi", "adapter": ADAPTER, "result": result, "fixed": fixed}

    if state == "wifi_up_no_net":
        push_alert("warning", "No Internet Access", "WiFi is connected but there is no internet. Restarting network stack.", state)
        result = restart_network()
        fixed = result.get("internet", False)
        if fixed:
            push_alert("resolved", "Internet Restored", "Network stack restarted. Internet is back.", "wifi_connected")
        else:
            push_alert("critical", "Network Fix Failed", "Could not restore internet automatically.", state)
        last_state = state
        return {"wifi_state": state, "action": "restart_network", "adapter": ADAPTER, "result": result, "fixed": fixed}

    ok, _ = run(["ping", "-n", "2", "-w", "2000", "8.8.8.8"])
    if ok:
        if last_state in ("wifi_disabled", "wifi_up_no_net"):
            push_alert("resolved", "Connection Healthy", "All systems are operating normally.", state)
        last_state = state
        return {"wifi_state": state, "action": "none", "reason": "Everything looks fine"}

    ok2, _ = flush_dns()
    push_alert("info", "DNS Flushed", "Connectivity issue detected. DNS cache cleared.", state)
    last_state = state
    return {"wifi_state": state, "action": "flush_dns_only", "flush_ok": ok2}


def get_diagnostics():
    state = get_wifi_state()
    ok_ping, _ = run(["ping", "-n", "1", "-w", "2000", "8.8.8.8"])
    ok_dns, _ = run(["nslookup", "google.com"])
    _, wlan_out = run(["netsh", "wlan", "show", "interfaces"])
    _, adapter_out = ps(f'Get-NetAdapter -Name "{ADAPTER}" -ErrorAction SilentlyContinue | Select-Object Name,Status,LinkSpeed | ConvertTo-Json')
    return {
        "version": VERSION,
        "adapter": ADAPTER,
        "wifi_state": state,
        "internet_ping": ok_ping,
        "dns_resolution": ok_dns,
        "wlan_interfaces_raw": wlan_out[:500],
        "adapter_info": adapter_out[:300]
    }


# ── Background monitor ───────────────────────────────────────────────────────
def background_monitor():
    global last_state
    time.sleep(10)
    while True:
        try:
            state = get_wifi_state()
            if state != last_state:
                log.info(f"[Monitor] State changed: {last_state} -> {state}")
                if state == "wifi_disabled":
                    push_alert("critical", "WiFi Disabled Detected", f"WiFi turned off on adapter '{ADAPTER}'.", state)
                elif state == "wifi_up_no_net":
                    push_alert("warning", "Internet Lost", "WiFi connected but no internet access.", state)
                elif state == "wifi_connected" and last_state in ("wifi_disabled", "wifi_up_no_net"):
                    push_alert("resolved", "Connection Restored", "Network is healthy again.", state)
                last_state = state
        except Exception as e:
            log.error(f"[Monitor] Error: {e}")
        time.sleep(15)


# ── Dashboard HTML ───────────────────────────────────────────────────────────
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Voltix Mechanic Agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Inter','Segoe UI',system-ui,sans-serif;background:#0a0e1a;color:#e2e8f0;min-height:100vh}
  #alert-banner{display:none;width:100%;padding:14px 24px;font-size:15px;font-weight:600;text-align:center;position:sticky;top:0;z-index:1000;animation:slideDown 0.4s ease;backdrop-filter:blur(8px)}
  #alert-banner.critical{background:rgba(220,38,38,.92);color:#fff}
  #alert-banner.warning{background:rgba(217,119,6,.92);color:#fff}
  #alert-banner.resolved{background:rgba(22,163,74,.92);color:#fff}
  #alert-banner.info{background:rgba(37,99,235,.92);color:#fff}
  @keyframes slideDown{from{transform:translateY(-100%);opacity:0}to{transform:translateY(0);opacity:1}}
  .header{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);border-bottom:1px solid rgba(56,189,248,.15);padding:20px 32px;display:flex;align-items:center;gap:16px}
  .logo{font-size:22px;font-weight:700;color:#38bdf8;letter-spacing:-.3px}
  .logo span{color:#64748b;font-weight:400;font-size:14px;margin-left:8px}
  .version-badge{background:rgba(56,189,248,.12);color:#38bdf8;padding:3px 10px;border-radius:20px;font-size:12px;margin-left:auto;border:1px solid rgba(56,189,248,.25)}
  .container{max-width:1100px;margin:0 auto;padding:28px 24px}
  .status-card{border-radius:16px;padding:28px 32px;margin-bottom:24px;display:flex;align-items:center;gap:24px;border:1px solid transparent;transition:all 0.4s ease;backdrop-filter:blur(12px)}
  .status-card.healthy{background:rgba(5,46,22,.6);border-color:rgba(22,163,74,.5);box-shadow:0 0 40px rgba(22,163,74,.08)}
  .status-card.degraded{background:rgba(28,25,23,.6);border-color:rgba(217,119,6,.5);box-shadow:0 0 40px rgba(217,119,6,.08)}
  .status-card.critical{background:rgba(28,5,5,.6);border-color:rgba(220,38,38,.5);box-shadow:0 0 40px rgba(220,38,38,.08)}
  .status-card.unknown{background:rgba(15,23,42,.6);border-color:#334155}
  .status-icon{font-size:48px;flex-shrink:0}
  .status-title{font-size:22px;font-weight:700;margin-bottom:4px}
  .status-sub{font-size:14px;color:#94a3b8}
  .status-time{margin-left:auto;text-align:right;font-size:12px;color:#64748b}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
  @media(max-width:768px){.metrics{grid-template-columns:repeat(2,1fr)}}
  .metric{background:rgba(15,23,42,.7);border:1px solid rgba(30,58,95,.6);border-radius:12px;padding:18px 20px;transition:border-color .3s}
  .metric:hover{border-color:rgba(56,189,248,.35)}
  .metric-label{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:8px}
  .metric-value{font-size:20px;font-weight:700;transition:color .3s}
  .metric-value.ok{color:#4ade80}
  .metric-value.bad{color:#f87171}
  .metric-value.neutral{color:#94a3b8}
  .section-title{font-size:14px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:14px}
  .alerts-list{display:flex;flex-direction:column;gap:10px}
  .alert-item{background:rgba(15,23,42,.7);border:1px solid #1e293b;border-radius:10px;padding:14px 18px;display:flex;align-items:flex-start;gap:14px;border-left:4px solid transparent;transition:background .2s}
  .alert-item:hover{background:rgba(15,23,42,.9)}
  .alert-item.critical{border-left-color:#dc2626}
  .alert-item.warning{border-left-color:#f59e0b}
  .alert-item.resolved{border-left-color:#4ade80}
  .alert-item.info{border-left-color:#60a5fa}
  .alert-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:4px}
  .alert-dot.critical{background:#dc2626;box-shadow:0 0 8px #dc2626}
  .alert-dot.warning{background:#f59e0b;box-shadow:0 0 8px #f59e0b}
  .alert-dot.resolved{background:#4ade80}
  .alert-dot.info{background:#60a5fa}
  .alert-title{font-weight:600;font-size:14px;margin-bottom:2px}
  .alert-msg{font-size:13px;color:#94a3b8}
  .alert-time{margin-left:auto;font-size:11px;color:#475569;white-space:nowrap;padding-left:12px}
  .level-badge{font-size:10px;font-weight:700;text-transform:uppercase;padding:2px 7px;border-radius:4px}
  .level-badge.critical{background:#450a0a;color:#fca5a5}
  .level-badge.warning{background:#451a03;color:#fcd34d}
  .level-badge.resolved{background:#052e16;color:#86efac}
  .level-badge.info{background:#0c1a3a;color:#93c5fd}
  .empty-state{text-align:center;padding:40px;color:#475569;font-size:14px}
  .actions{display:flex;gap:12px;margin-bottom:24px}
  .btn{padding:10px 22px;border-radius:8px;border:none;cursor:pointer;font-size:14px;font-weight:600;transition:all 0.2s}
  .btn-primary{background:#2563eb;color:#fff}
  .btn-primary:hover{background:#1d4ed8;box-shadow:0 0 20px rgba(37,99,235,.25)}
  .btn-primary:disabled{background:#1e3a5f;color:#475569;cursor:not-allowed}
  .btn-secondary{background:#1e293b;color:#94a3b8;border:1px solid #334155}
  .btn-secondary:hover{background:#263348}
  .spinner{display:inline-block;width:14px;height:14px;border:2px solid #ffffff44;border-top-color:#fff;border-radius:50%;animation:spin 0.7s linear infinite;vertical-align:middle;margin-right:6px}
  @keyframes spin{to{transform:rotate(360deg)}}
  .footer{text-align:center;padding:24px;color:#334155;font-size:12px}
  .pulse{animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
</style>
</head>
<body>
<div id="alert-banner"></div>
<div class="header">
  <div class="logo">&#9889; Voltix Mechanic <span>by ArmorIQ</span></div>
  <div class="version-badge">v5.1.0</div>
</div>
<div class="container">
  <div class="status-card unknown" id="status-card">
    <div class="status-icon" id="status-icon">&#8987;</div>
    <div>
      <div class="status-title" id="status-title">Checking system...</div>
      <div class="status-sub" id="status-sub">Running diagnostics</div>
    </div>
    <div class="status-time" id="status-time">-</div>
  </div>
  <div class="metrics">
    <div class="metric"><div class="metric-label">WiFi State</div><div class="metric-value neutral" id="m-wifi">-</div></div>
    <div class="metric"><div class="metric-label">Internet Ping</div><div class="metric-value neutral" id="m-ping">-</div></div>
    <div class="metric"><div class="metric-label">DNS Resolution</div><div class="metric-value neutral" id="m-dns">-</div></div>
    <div class="metric"><div class="metric-label">Adapter</div><div class="metric-value neutral" id="m-adapter">-</div></div>
  </div>
  <div class="actions">
    <button class="btn btn-primary" id="heal-btn" onclick="triggerHeal()">&#128295; Run Auto-Heal</button>
    <button class="btn btn-secondary" onclick="refresh()">&#8635; Refresh</button>
  </div>
  <div class="section-title">Alert Log</div>
  <div class="alerts-list" id="alerts-list">
    <div class="empty-state">No alerts yet &mdash; system monitoring active</div>
  </div>
</div>
<div class="footer">Voltix Mechanic Agent &middot; ArmorIQ Infrastructure &middot; Auto-refreshes every 10s</div>
<script>
const API_KEY='%%API_KEY%%';
async function fetchJSON(url,opts={}){
  const res=await fetch(url,{headers:{'X-API-Key':API_KEY,'Content-Type':'application/json'},...opts});
  return res.json();
}
function showBanner(level,text){
  const b=document.getElementById('alert-banner');
  b.className=level;b.textContent=text;b.style.display='block';
  if(level==='resolved'||level==='info')setTimeout(()=>{b.style.display='none'},5000);
}
function updateStatus(diag){
  const card=document.getElementById('status-card');
  const icon=document.getElementById('status-icon');
  const title=document.getElementById('status-title');
  const sub=document.getElementById('status-sub');
  const ts=document.getElementById('status-time');
  card.className='status-card';
  const s=diag.wifi_state;
  if(s==='wifi_connected'){
    card.classList.add('healthy');icon.textContent='✅';
    title.textContent='All Systems Healthy';
    sub.textContent='Connected · Internet OK · DNS OK';
    showBanner('resolved','✅ Network is healthy — no issues detected');
  }else if(s==='wifi_up_no_net'){
    card.classList.add('degraded');icon.textContent='⚠️';
    title.textContent='WiFi On — No Internet';
    sub.textContent='Connected to router but cannot reach internet';
    showBanner('warning','⚠️ WiFi connected but no internet access detected');
  }else if(s==='wifi_disabled'){
    card.classList.add('critical');icon.textContent='🔴';
    title.textContent='WiFi is Disabled';
    sub.textContent="Adapter '"+diag.adapter+"' is turned off";
    showBanner('critical','🔴 CRITICAL: WiFi adapter is disabled — connection lost');
  }else{
    card.classList.add('unknown');icon.textContent='❓';
    title.textContent='Unknown State';sub.textContent=s;
  }
  ts.innerHTML='Last checked<br>'+new Date().toLocaleTimeString();
  const wifiEl=document.getElementById('m-wifi');
  wifiEl.textContent=s.replace(/_/g,' ').toUpperCase();
  wifiEl.className='metric-value '+(s==='wifi_connected'?'ok':'bad');
  const pingEl=document.getElementById('m-ping');
  pingEl.textContent=diag.internet_ping?'REACHABLE':'FAILED';
  pingEl.className='metric-value '+(diag.internet_ping?'ok':'bad');
  const dnsEl=document.getElementById('m-dns');
  dnsEl.textContent=diag.dns_resolution?'OK':'FAILED';
  dnsEl.className='metric-value '+(diag.dns_resolution?'ok':'bad');
  document.getElementById('m-adapter').textContent=diag.adapter;
  document.getElementById('m-adapter').className='metric-value neutral';
}
function renderAlerts(alertList){
  const el=document.getElementById('alerts-list');
  if(!alertList||alertList.length===0){
    el.innerHTML='<div class="empty-state">No alerts yet &mdash; system monitoring active</div>';return;
  }
  el.innerHTML=alertList.map(a=>`
    <div class="alert-item ${a.level}">
      <div class="alert-dot ${a.level}"></div>
      <div style="flex:1">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
          <span class="alert-title">${a.title}</span>
          <span class="level-badge ${a.level}">${a.level}</span>
        </div>
        <div class="alert-msg">${a.message}</div>
      </div>
      <div class="alert-time">${a.timestamp}</div>
    </div>
  `).join('');
}
async function refresh(){
  try{
    const diag=await fetchJSON('/diagnostics');
    updateStatus(diag);
    const alertData=await fetchJSON('/alerts');
    renderAlerts(alertData.alerts);
  }catch(e){console.error('Refresh failed',e);}
}
async function triggerHeal(){
  const btn=document.getElementById('heal-btn');
  btn.disabled=true;
  btn.innerHTML='<span class="spinner"></span>Healing...';
  try{
    await fetchJSON('/auto-heal',{method:'POST'});
    await refresh();
  }catch(e){console.error('Heal failed',e);}
  btn.disabled=false;
  btn.innerHTML='&#128295; Run Auto-Heal';
}
refresh();
setInterval(refresh,10000);
</script>
</body>
</html>"""


# ── HTTP Handler ─────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(f"HTTP {self.address_string()} {fmt % args}")

    def send_json(self, code, obj):
        body = json.dumps(obj, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        key = self.headers.get("X-API-Key", "")
        if key != API_KEY:
            self.send_json(401, {"error": "Unauthorized"})
            return False
        return True

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-API-Key, Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/dashboard"):
            html = DASHBOARD_HTML.replace("%%API_KEY%%", API_KEY)
            self.send_html(html)
            return
        if path == "/health":
            self.send_json(200, {"status": "ok", "version": VERSION, "adapter": ADAPTER})
            return
        if not self.auth(): return
        if path == "/diagnostics":
            self.send_json(200, get_diagnostics())
        elif path == "/alerts":
            with alert_lock:
                self.send_json(200, {"alerts": list(alerts), "count": len(alerts)})
        elif path == "/adapter":
            self.send_json(200, {"adapter": ADAPTER, "state": get_wifi_state()})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.auth(): return
        if path == "/auto-heal":
            result = auto_heal()
            self.send_json(200, result)
        elif path == "/flush-dns":
            ok, out = flush_dns()
            self.send_json(200, {"ok": ok, "output": out})
        elif path == "/enable-wifi":
            result = enable_wifi()
            self.send_json(200, result)
        elif path == "/restart-network":
            result = restart_network()
            self.send_json(200, result)
        elif path == "/alerts/clear":
            with alert_lock:
                alerts.clear()
            self.send_json(200, {"cleared": True})
        else:
            self.send_json(404, {"error": "Not found"})


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Admin check ──────────────────────────────────────────────────
    import ctypes
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        log.warning("=" * 60)
        log.warning("NOT running as Administrator!")
        log.warning("WiFi healing WILL NOT WORK without admin privileges.")
        log.warning("=" * 60)
    else:
        log.info("Running as Administrator ✓")

    # ── Verify winrt is installed ────────────────────────────────────
    try:
        from winrt.windows.devices.radios import Radio, RadioState, RadioKind
        log.info("winrt-Windows.Devices.Radios is installed ✓")
    except ImportError:
        log.warning("=" * 60)
        log.warning("winrt-Windows.Devices.Radios is NOT installed!")
        log.warning("WiFi radio toggle will NOT work without it.")
        log.warning('Run: python -m pip install winrt-runtime "winrt-Windows.Devices.Radios"')
        log.warning("=" * 60)

    # ── Start background monitor ─────────────────────────────────────
    t = threading.Thread(target=background_monitor, daemon=True)
    t.start()
    log.info("Background network monitor started (checks every 15s)")

    # ── Start HTTP server ────────────────────────────────────────────
    log.info(f"Voltix Mechanic Agent {VERSION} starting on port {PORT}")
    log.info(f"Adapter: {ADAPTER}  |  API key: {'set' if API_KEY else 'NOT SET'}")
    log.info(f">>> Dashboard: http://localhost:{PORT}/")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")
