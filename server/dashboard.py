"""
server/dashboard.py
Premium dark-mode dashboard HTML served at GET / and GET /dashboard.
Includes ArmorIQ Intent Verification panel with real-time cryptographic
proof chain visualization, simulation controls, and security block demo.

The placeholder %%API_KEY%% is replaced at serve-time with the real key.
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Voltix Mechanic Agent – ArmorIQ</title>
<meta name="description" content="Autonomous self-healing WiFi and network infrastructure agent with cryptographic intent verification by ArmorIQ.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Inter','Segoe UI',system-ui,sans-serif;background:#060a14;color:#e2e8f0;min-height:100vh}

  /* ── Alert banner ── */
  #alert-banner{display:none;width:100%;padding:14px 24px;font-size:15px;font-weight:600;
    text-align:center;position:sticky;top:0;z-index:1000;
    animation:slideDown 0.35s ease;backdrop-filter:blur(12px);letter-spacing:.2px}
  #alert-banner.critical{background:rgba(220,38,38,.93);color:#fff}
  #alert-banner.warning{background:rgba(217,119,6,.93);color:#fff}
  #alert-banner.resolved{background:rgba(22,163,74,.93);color:#fff}
  #alert-banner.info{background:rgba(37,99,235,.93);color:#fff}
  #alert-banner.blocked{background:rgba(168,85,247,.93);color:#fff}
  @keyframes slideDown{from{transform:translateY(-100%);opacity:0}to{transform:translateY(0);opacity:1}}

  /* ── Header ── */
  .header{background:linear-gradient(135deg,#080e1e 0%,#0f1729 100%);
    border-bottom:1px solid rgba(56,189,248,.1);
    padding:14px 28px;display:flex;align-items:center;gap:14px}
  .logo{font-size:19px;font-weight:800;background:linear-gradient(135deg,#38bdf8,#818cf8);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-.5px}
  .logo-sub{color:#475569;font-weight:400;font-size:12px;margin-left:8px;
    -webkit-text-fill-color:#475569}
  .header-right{margin-left:auto;display:flex;align-items:center;gap:10px}
  .version-badge{background:rgba(56,189,248,.08);color:#38bdf8;padding:3px 10px;
    border-radius:20px;font-size:10px;border:1px solid rgba(56,189,248,.15);font-weight:600}
  .armoriq-badge{background:rgba(129,140,248,.08);color:#a5b4fc;padding:3px 10px;
    border-radius:20px;font-size:10px;border:1px solid rgba(129,140,248,.15);font-weight:600;
    display:flex;align-items:center;gap:4px}
  .armoriq-badge .dot{width:6px;height:6px;border-radius:50%;background:#818cf8;
    box-shadow:0 0 6px #818cf8}
  .demo-badge{background:rgba(251,146,60,.12);color:#fb923c;padding:3px 10px;
    border-radius:20px;font-size:10px;border:1px solid rgba(251,146,60,.2);font-weight:700;
    animation:pulse-badge 2s infinite}
  @keyframes pulse-badge{0%,100%{opacity:1}50%{opacity:.6}}
  .live-dot{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 7px #4ade80;
    animation:pulse-dot 2s infinite}
  @keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.85)}}

  /* ── Layout ── */
  .container{max-width:1240px;margin:0 auto;padding:20px 22px}

  /* ── Status card ── */
  .status-card{border-radius:14px;padding:20px 24px;margin-bottom:16px;
    display:flex;align-items:center;gap:18px;border:1px solid transparent;
    transition:all .4s ease;position:relative;overflow:hidden}
  .status-card::before{content:'';position:absolute;inset:0;opacity:.04;
    background:radial-gradient(circle at 20% 50%,#fff,transparent 60%)}
  .status-card.healthy{background:rgba(5,46,22,.6);border-color:rgba(22,163,74,.4)}
  .status-card.degraded{background:rgba(28,20,5,.6);border-color:rgba(217,119,6,.4)}
  .status-card.critical{background:rgba(28,5,5,.6);border-color:rgba(220,38,38,.4)}
  .status-card.unknown{background:rgba(15,23,42,.6);border-color:#1e3a5f}
  .status-icon{font-size:38px;flex-shrink:0}
  .status-title{font-size:18px;font-weight:700;margin-bottom:3px;letter-spacing:-.3px}
  .status-sub{font-size:12px;color:#94a3b8}
  .status-time{margin-left:auto;text-align:right;font-size:10px;color:#475569;flex-shrink:0}

  /* ── Last verified card ── */
  .last-verified{background:rgba(129,140,248,.04);border:1px solid rgba(129,140,248,.15);
    border-radius:12px;padding:14px 18px;margin-bottom:16px;display:none;
    animation:fadeIn .4s ease}
  .last-verified.visible{display:flex;align-items:center;gap:14px}
  .lv-icon{font-size:28px}
  .lv-info{flex:1}
  .lv-title{font-size:13px;font-weight:700;color:#c7d2fe;margin-bottom:2px}
  .lv-sub{font-size:11px;color:#818cf8;font-family:'JetBrains Mono',monospace}
  .lv-badge{padding:4px 10px;border-radius:6px;font-size:10px;font-weight:700;text-transform:uppercase}
  .lv-badge.verified{background:rgba(74,222,128,.12);color:#4ade80;border:1px solid rgba(74,222,128,.2)}
  .lv-badge.blocked{background:rgba(248,113,113,.12);color:#f87171;border:1px solid rgba(248,113,113,.2)}
  @keyframes fadeIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}

  /* ── Metrics ── */
  .metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px}
  @media(max-width:900px){.metrics{grid-template-columns:repeat(3,1fr)}}
  @media(max-width:550px){.metrics{grid-template-columns:repeat(2,1fr)}}
  .metric{background:rgba(10,16,30,.85);border:1px solid rgba(30,58,95,.5);
    border-radius:10px;padding:14px 16px;transition:border-color .25s,transform .2s}
  .metric:hover{border-color:rgba(56,189,248,.25);transform:translateY(-1px)}
  .metric-label{font-size:9px;text-transform:uppercase;letter-spacing:1.1px;
    color:#475569;margin-bottom:6px;font-weight:600}
  .metric-value{font-size:16px;font-weight:700;transition:color .3s}
  .metric-value.ok{color:#4ade80}
  .metric-value.bad{color:#f87171}
  .metric-value.warn{color:#fbbf24}
  .metric-value.neutral{color:#64748b}
  .metric-value.purple{color:#a78bfa}

  /* ── Action buttons ── */
  .actions{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}
  .btn{padding:8px 16px;border-radius:7px;border:none;cursor:pointer;
    font-size:12px;font-weight:600;font-family:inherit;transition:all .2s}
  .btn-primary{background:linear-gradient(135deg,#2563eb,#4f46e5);color:#fff}
  .btn-primary:hover{box-shadow:0 0 20px rgba(37,99,235,.35);transform:translateY(-1px)}
  .btn-primary:disabled{background:#1e3a5f;color:#334155;cursor:not-allowed;transform:none;box-shadow:none}
  .btn-warning{background:linear-gradient(135deg,#d97706,#b45309);color:#fff}
  .btn-warning:hover{box-shadow:0 0 20px rgba(217,119,6,.35);transform:translateY(-1px)}
  .btn-warning:disabled{background:#3d1a03;color:#78350f;cursor:not-allowed;transform:none;box-shadow:none}
  .btn-danger-action{background:linear-gradient(135deg,#dc2626,#991b1b);color:#fff}
  .btn-danger-action:hover{box-shadow:0 0 20px rgba(220,38,38,.35);transform:translateY(-1px)}
  .btn-danger-action:disabled{background:#450a0a;color:#7f1d1d;cursor:not-allowed;transform:none;box-shadow:none}
  .btn-secondary{background:rgba(30,41,59,.9);color:#94a3b8;border:1px solid #334155;font-size:12px}
  .btn-secondary:hover{background:#263348;transform:translateY(-1px)}
  .btn-danger{background:rgba(127,29,29,.5);color:#fca5a5;border:1px solid rgba(220,38,38,.2);font-size:12px}
  .btn-danger:hover{background:rgba(153,27,27,.6);transform:translateY(-1px)}
  .spinner{display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,.25);
    border-top-color:#fff;border-radius:50%;animation:spin .65s linear infinite;
    vertical-align:middle;margin-right:5px}
  @keyframes spin{to{transform:rotate(360deg)}}

  /* ── Two-column layout ── */
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  @media(max-width:900px){.two-col{grid-template-columns:1fr}}

  /* ── Section panel ── */
  .panel{background:rgba(8,14,28,.9);border:1px solid rgba(30,58,95,.4);
    border-radius:12px;padding:16px;overflow:hidden}
  .panel-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
  .section-title{font-size:10px;font-weight:700;text-transform:uppercase;
    letter-spacing:1.1px;color:#475569;display:flex;align-items:center;gap:7px}
  .section-title .icon{font-size:13px}
  .badge-count{background:#1e293b;border:1px solid #334155;color:#64748b;
    padding:2px 7px;border-radius:10px;font-size:10px;font-weight:600}

  /* ── ArmorIQ Intent Verification panel ── */
  .armoriq-panel{border-color:rgba(129,140,248,.2)}
  .armoriq-panel .section-title{color:#818cf8}
  .armoriq-status-bar{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
  .armoriq-chip{background:rgba(129,140,248,.05);border:1px solid rgba(129,140,248,.1);
    border-radius:7px;padding:7px 10px;font-size:10px;color:#a5b4fc;flex:1;min-width:70px}
  .armoriq-chip .chip-label{font-size:8px;text-transform:uppercase;color:#6366f1;
    letter-spacing:.8px;margin-bottom:2px;font-weight:600}
  .armoriq-chip .chip-value{font-weight:700;font-size:14px;color:#c7d2fe}
  .armoriq-chip .chip-value.green{color:#4ade80}
  .armoriq-chip .chip-value.red{color:#f87171}
  .armoriq-chip .chip-value.purple{color:#a78bfa}

  /* ── Proof chain visualization ── */
  .proof-chain{display:flex;align-items:center;gap:0;margin:8px 0;flex-wrap:wrap;
    padding:10px 12px;background:rgba(129,140,248,.03);border:1px solid rgba(129,140,248,.08);
    border-radius:8px}
  .proof-node{background:rgba(129,140,248,.08);border:1px solid rgba(129,140,248,.2);
    border-radius:5px;padding:4px 9px;font-size:9px;font-weight:600;color:#a5b4fc;
    white-space:nowrap;transition:all .2s}
  .proof-node.ok{border-color:rgba(74,222,128,.35);color:#86efac;background:rgba(74,222,128,.06)}
  .proof-node.fail{border-color:rgba(248,113,113,.35);color:#fca5a5;background:rgba(248,113,113,.06)}
  .proof-node.skip{border-color:rgba(100,116,139,.3);color:#94a3b8;background:rgba(100,116,139,.06)}
  .proof-node.active{animation:proof-pulse .6s ease;box-shadow:0 0 12px rgba(129,140,248,.3)}
  @keyframes proof-pulse{0%{transform:scale(1)}50%{transform:scale(1.12)}100%{transform:scale(1)}}
  .proof-arrow{color:#334155;font-size:10px;padding:0 2px;flex-shrink:0}

  /* ── Intent log items ── */
  .intent-item{background:rgba(10,12,25,.9);border:1px solid rgba(129,140,248,.1);
    border-radius:8px;padding:10px 12px;margin-bottom:6px;
    border-left:3px solid transparent;transition:all .15s}
  .intent-item:hover{background:rgba(15,18,35,.9)}
  .intent-item.verified{border-left-color:#818cf8}
  .intent-item.blocked{border-left-color:#f87171}
  .intent-item.error{border-left-color:#fbbf24}
  .intent-header{display:flex;align-items:center;gap:6px;margin-bottom:5px;flex-wrap:wrap}
  .intent-action{font-weight:700;font-size:12px;color:#e2e8f0;font-family:'JetBrains Mono',monospace}
  .intent-badge{font-size:8px;font-weight:700;text-transform:uppercase;padding:2px 6px;
    border-radius:3px;letter-spacing:.4px}
  .intent-badge.production{background:#1a1a3e;color:#818cf8}
  .intent-badge.local_simulation{background:#0a1930;color:#38bdf8}
  .intent-badge.security_enforcement{background:#3f0b0b;color:#fca5a5}
  .intent-badge.v-verified{background:rgba(74,222,128,.1);color:#4ade80;border:1px solid rgba(74,222,128,.2)}
  .intent-badge.v-blocked{background:rgba(248,113,113,.1);color:#f87171;border:1px solid rgba(248,113,113,.2)}
  .intent-badge.v-error{background:rgba(251,191,36,.1);color:#fbbf24;border:1px solid rgba(251,191,36,.2)}
  .intent-details{display:grid;grid-template-columns:1fr 1fr;gap:3px 10px;
    font-size:10px;color:#64748b}
  .intent-details .label{color:#475569}
  .intent-details .value{color:#94a3b8;font-family:'JetBrains Mono',monospace;font-size:9px}
  .intent-time{font-size:9px;color:#334155;margin-left:auto}

  /* ── Alert log ── */
  .alerts-list{display:flex;flex-direction:column;gap:6px;max-height:400px;overflow-y:auto}
  .alerts-list::-webkit-scrollbar{width:3px}
  .alerts-list::-webkit-scrollbar-thumb{background:#1e3a5f;border-radius:3px}
  .alert-item{background:rgba(10,16,30,.85);border:1px solid #1e293b;border-radius:8px;
    padding:10px 12px;display:flex;align-items:flex-start;gap:10px;
    border-left:3px solid transparent;transition:background .15s}
  .alert-item:hover{background:rgba(15,25,50,.9)}
  .alert-item.critical{border-left-color:#dc2626}
  .alert-item.warning{border-left-color:#f59e0b}
  .alert-item.resolved{border-left-color:#4ade80}
  .alert-item.info{border-left-color:#60a5fa}
  .alert-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:4px}
  .alert-dot.critical{background:#dc2626;box-shadow:0 0 5px #dc2626}
  .alert-dot.warning{background:#f59e0b;box-shadow:0 0 5px #f59e0b}
  .alert-dot.resolved{background:#4ade80}
  .alert-dot.info{background:#60a5fa}
  .alert-title{font-weight:600;font-size:11px;margin-bottom:2px}
  .alert-msg{font-size:10px;color:#94a3b8;line-height:1.4}
  .alert-time{margin-left:auto;font-size:9px;color:#334155;white-space:nowrap;padding-left:8px}
  .level-badge{font-size:8px;font-weight:700;text-transform:uppercase;padding:2px 5px;border-radius:3px}
  .level-badge.critical{background:#3f0b0b;color:#fca5a5}
  .level-badge.warning{background:#3d1a03;color:#fcd34d}
  .level-badge.resolved{background:#042310;color:#86efac}
  .level-badge.info{background:#0a1630;color:#93c5fd}
  .empty-state{text-align:center;padding:30px 0;color:#2d3748;font-size:12px}
  .empty-state span{display:block;font-size:24px;margin-bottom:8px;opacity:.3}

  /* ── Intent log scrollbar + list ── */
  .intent-list{display:flex;flex-direction:column;gap:6px;max-height:400px;overflow-y:auto}
  .intent-list::-webkit-scrollbar{width:3px}
  .intent-list::-webkit-scrollbar-thumb{background:#1e3a5f;border-radius:3px}

  /* ── Footer ── */
  .footer{text-align:center;padding:24px 0 16px;color:#1e293b;font-size:10px;letter-spacing:.3px}
</style>
</head>
<body>
<div id="alert-banner"></div>
<div class="header">
  <div class="logo">&#9889; Voltix Mechanic <span class="logo-sub">by ArmorIQ</span></div>
  <div class="header-right">
    <div class="demo-badge" id="demo-badge" style="display:none">DEMO MODE</div>
    <div class="armoriq-badge" id="armoriq-header-badge">
      <span class="dot"></span>
      <span id="armoriq-mode-label">ArmorIQ</span>
    </div>
    <div class="live-dot" title="Live monitoring active"></div>
    <div class="version-badge">v6.1.0</div>
  </div>
</div>

<div class="container">
  <!-- Status card -->
  <div class="status-card unknown" id="status-card">
    <div class="status-icon" id="status-icon">&#8987;</div>
    <div>
      <div class="status-title" id="status-title">Checking system&hellip;</div>
      <div class="status-sub" id="status-sub">Running diagnostics</div>
    </div>
    <div class="status-time" id="status-time">&ndash;</div>
  </div>

  <!-- Last verified action card -->
  <div class="last-verified" id="last-verified">
    <div class="lv-icon" id="lv-icon">&#128274;</div>
    <div class="lv-info">
      <div class="lv-title" id="lv-title">&ndash;</div>
      <div class="lv-sub" id="lv-sub">&ndash;</div>
    </div>
    <div class="lv-badge verified" id="lv-badge">VERIFIED</div>
  </div>

  <!-- Metrics -->
  <div class="metrics">
    <div class="metric">
      <div class="metric-label">WiFi State</div>
      <div class="metric-value neutral" id="m-wifi">&ndash;</div>
    </div>
    <div class="metric">
      <div class="metric-label">Internet</div>
      <div class="metric-value neutral" id="m-ping">&ndash;</div>
    </div>
    <div class="metric">
      <div class="metric-label">DNS</div>
      <div class="metric-value neutral" id="m-dns">&ndash;</div>
    </div>
    <div class="metric">
      <div class="metric-label">Verified</div>
      <div class="metric-value purple" id="m-verified">0</div>
    </div>
    <div class="metric">
      <div class="metric-label">Blocked</div>
      <div class="metric-value neutral" id="m-blocked">0</div>
    </div>
  </div>

  <!-- Actions -->
  <div class="actions">
    <button class="btn btn-primary" id="heal-btn" onclick="triggerHeal()">&#128295; Auto-Heal</button>
    <button class="btn btn-warning" id="sim-btn" onclick="simulateFailure()">&#9889; Simulate Failure</button>
    <button class="btn btn-danger-action" id="unsafe-btn" onclick="unsafeAction()">&#128274; Test Unsafe Action</button>
    <button class="btn btn-secondary" onclick="refresh()">&#8635; Refresh</button>
    <button class="btn btn-danger" onclick="clearAll()" style="margin-left:auto">&#128465; Clear</button>
  </div>

  <!-- Two-column: Alerts + Intent Verification -->
  <div class="two-col">
    <!-- Alert Log -->
    <div class="panel">
      <div class="panel-header">
        <div class="section-title"><span class="icon">&#128276;</span> Alert Log</div>
        <div class="badge-count" id="alert-count">0</div>
      </div>
      <div class="alerts-list" id="alerts-list">
        <div class="empty-state"><span>&#128225;</span>No alerts yet</div>
      </div>
    </div>

    <!-- ArmorIQ Intent Verification -->
    <div class="panel armoriq-panel">
      <div class="panel-header">
        <div class="section-title"><span class="icon">&#128274;</span> Intent Verification</div>
        <div class="badge-count" id="intent-count">0</div>
      </div>
      <div class="armoriq-status-bar" id="armoriq-status-bar">
        <div class="armoriq-chip">
          <div class="chip-label">Mode</div>
          <div class="chip-value" id="aiq-mode">&ndash;</div>
        </div>
        <div class="armoriq-chip">
          <div class="chip-label">Verified</div>
          <div class="chip-value green" id="aiq-verified">0</div>
        </div>
        <div class="armoriq-chip">
          <div class="chip-label">Blocked</div>
          <div class="chip-value red" id="aiq-blocked">0</div>
        </div>
        <div class="armoriq-chip">
          <div class="chip-label">SDK</div>
          <div class="chip-value" id="aiq-sdk">&ndash;</div>
        </div>
      </div>
      <!-- Live proof chain -->
      <div class="proof-chain" id="proof-chain" style="display:none"></div>
      <div class="intent-list" id="intent-list">
        <div class="empty-state"><span>&#128274;</span>No verifications yet &mdash; press Simulate Failure</div>
      </div>
    </div>
  </div>
</div>

<div class="footer">Voltix Mechanic Agent &middot; ArmorIQ Cryptographic Intent Verification &middot; Auto-refreshes every 6s</div>

<script>
const API_KEY = '%%API_KEY%%';

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, {
    headers: { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' },
    ...opts
  });
  return res.json();
}

function showBanner(level, text) {
  const b = document.getElementById('alert-banner');
  b.className = level;
  b.textContent = text;
  b.style.display = 'block';
  if (level === 'resolved' || level === 'info') {
    setTimeout(() => { b.style.display = 'none'; }, 4500);
  }
  if (level === 'blocked') {
    setTimeout(() => { b.style.display = 'none'; }, 6000);
  }
}

function updateStatus(diag) {
  const card  = document.getElementById('status-card');
  const icon  = document.getElementById('status-icon');
  const title = document.getElementById('status-title');
  const sub   = document.getElementById('status-sub');
  const ts    = document.getElementById('status-time');

  card.className = 'status-card';
  const s = diag.wifi_state;

  if (s === 'wifi_connected') {
    card.classList.add('healthy');
    icon.textContent = '\u2705';
    title.textContent = 'All Systems Healthy';
    sub.textContent = 'Connected \u00b7 Internet OK \u00b7 DNS OK';
  } else if (s === 'wifi_up_no_net') {
    card.classList.add('degraded');
    icon.textContent = '\u26a0\ufe0f';
    title.textContent = 'WiFi On \u2014 No Internet';
    sub.textContent = 'Connected to router but cannot reach internet';
    showBanner('warning', '\u26a0\ufe0f WiFi connected but no internet access detected');
  } else if (s === 'wifi_disabled') {
    card.classList.add('critical');
    icon.textContent = '\ud83d\udd34';
    title.textContent = 'WiFi is Disabled';
    sub.textContent = "Adapter '" + diag.adapter + "' is turned off";
    showBanner('critical', '\ud83d\udd34 CRITICAL: WiFi adapter is disabled');
  } else {
    card.classList.add('unknown');
    icon.textContent = '\u2753';
    title.textContent = 'Unknown State';
    sub.textContent = s;
  }

  ts.innerHTML = 'Last checked<br>' + new Date().toLocaleTimeString();

  const wEl = document.getElementById('m-wifi');
  wEl.textContent = s.replace(/_/g, ' ').toUpperCase();
  wEl.className = 'metric-value ' + (s === 'wifi_connected' ? 'ok' : 'bad');

  const pEl = document.getElementById('m-ping');
  pEl.textContent = diag.internet_ping ? 'REACHABLE' : 'FAILED';
  pEl.className = 'metric-value ' + (diag.internet_ping ? 'ok' : 'bad');

  const dEl = document.getElementById('m-dns');
  dEl.textContent = diag.dns_resolution ? 'OK' : 'FAILED';
  dEl.className = 'metric-value ' + (diag.dns_resolution ? 'ok' : 'bad');
}

function renderAlerts(alertList) {
  const el = document.getElementById('alerts-list');
  const ct = document.getElementById('alert-count');
  const n = alertList ? alertList.length : 0;
  ct.textContent = n;
  if (n === 0) {
    el.innerHTML = '<div class="empty-state"><span>\ud83d\udce1</span>No alerts yet</div>';
    return;
  }
  el.innerHTML = alertList.map(a => `
    <div class="alert-item ${a.level}">
      <div class="alert-dot ${a.level}"></div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:5px;margin-bottom:2px;flex-wrap:wrap">
          <span class="alert-title">${a.title}</span>
          <span class="level-badge ${a.level}">${a.level}</span>
        </div>
        <div class="alert-msg">${a.message}</div>
      </div>
      <div class="alert-time">${a.timestamp}</div>
    </div>
  `).join('');
}

function updateLastVerified(logs) {
  const lv = document.getElementById('last-verified');
  if (!logs || logs.length === 0) { lv.classList.remove('visible'); return; }
  const latest = logs[0];
  lv.classList.add('visible');
  document.getElementById('lv-icon').textContent = latest.status === 'blocked' ? '\ud83d\uded1' : '\ud83d\udd12';
  document.getElementById('lv-title').textContent = latest.action + ' \u2014 ' + (latest.description || '').substring(0, 60);
  document.getElementById('lv-sub').textContent = 'Token: ' + (latest.token_id || 'none') + ' | Hash: ' + (latest.plan_hash || 'none') + '...';
  const badge = document.getElementById('lv-badge');
  if (latest.status === 'blocked') {
    badge.className = 'lv-badge blocked';
    badge.textContent = '\ud83d\uded1 BLOCKED';
  } else if (latest.status === 'verified') {
    badge.className = 'lv-badge verified';
    badge.textContent = '\u2705 INTENT VERIFIED';
  } else {
    badge.className = 'lv-badge blocked';
    badge.textContent = '\u26a0 ERROR';
  }
}

function renderIntentLogs(logs, status) {
  const el = document.getElementById('intent-list');
  const ct = document.getElementById('intent-count');
  const n = logs ? logs.length : 0;
  ct.textContent = n;

  // Update ArmorIQ status chips
  if (status) {
    document.getElementById('aiq-mode').textContent =
      status.mode === 'production' ? 'Production' : 'Simulation';
    document.getElementById('aiq-verified').textContent = status.total_verifications || 0;
    document.getElementById('aiq-blocked').textContent = status.total_blocked || 0;
    document.getElementById('aiq-sdk').textContent = 'v' + (status.sdk_version || '?');
    const modeLabel = document.getElementById('armoriq-mode-label');
    modeLabel.textContent = status.mode === 'production' ? 'ArmorIQ Live' : 'ArmorIQ Sim';
    // Demo badge
    const demoBadge = document.getElementById('demo-badge');
    demoBadge.style.display = status.demo_mode ? 'inline-block' : 'none';
    // Metric counters
    document.getElementById('m-verified').textContent = status.total_verifications || 0;
    document.getElementById('m-blocked').textContent = status.total_blocked || 0;
    const mbEl = document.getElementById('m-blocked');
    mbEl.className = 'metric-value ' + ((status.total_blocked || 0) > 0 ? 'bad' : 'neutral');
  }

  updateLastVerified(logs);

  if (n === 0) {
    el.innerHTML = '<div class="empty-state"><span>\ud83d\udd10</span>No verifications yet \u2014 press Simulate Failure</div>';
    return;
  }

  el.innerHTML = logs.map(lg => {
    const modeClass = lg.mode || 'local_simulation';
    const statusClass = lg.status || 'verified';
    const modeName = modeClass === 'production' ? 'LIVE' :
                     modeClass === 'security_enforcement' ? 'SECURITY' : 'SIM';
    const statusIcon = statusClass === 'verified' ? '\u2705' :
                       statusClass === 'blocked' ? '\ud83d\uded1' : '\u26a0\ufe0f';
    const statusLabel = statusClass === 'verified' ? 'VERIFIED' :
                        statusClass === 'blocked' ? 'BLOCKED' : 'ERROR';
    return `
      <div class="intent-item ${statusClass}">
        <div class="intent-header">
          <span class="intent-action">${lg.action}</span>
          <span class="intent-badge ${modeClass}">${modeName}</span>
          <span class="intent-badge v-${statusClass}">${statusIcon} ${statusLabel}</span>
          <span class="intent-time">${lg.timestamp}</span>
        </div>
        <div class="intent-details">
          <span class="label">Plan Hash</span>
          <span class="value">${lg.plan_hash || '\u2013'}...</span>
          <span class="label">Token</span>
          <span class="value">${lg.token_id || 'none'}</span>
          <span class="label">Signature</span>
          <span class="value">${lg.signature_prefix || '\u2013'}...</span>
          <span class="label">Steps</span>
          <span class="value">${lg.steps_count || 0} verified</span>
        </div>
        ${lg.error ? `<div style="color:#f87171;font-size:10px;margin-top:3px">\u26a0 ${lg.error}</div>` : ''}
      </div>
    `;
  }).join('');
}

function showProofChain(verification) {
  if (!verification || !verification.steps || verification.steps.length === 0) return;
  const container = document.getElementById('proof-chain');
  container.style.display = 'flex';
  container.innerHTML = '';

  verification.steps.forEach((step, i) => {
    if (i > 0) {
      const arrow = document.createElement('span');
      arrow.className = 'proof-arrow';
      arrow.textContent = '\u2192';
      container.appendChild(arrow);
    }
    const node = document.createElement('span');
    const cls = step.status === 'ok' ? 'ok' : step.status === 'skipped' ? 'skip' : 'fail';
    node.className = `proof-node ${cls} active`;
    node.textContent = step.step;
    node.title = step.detail || '';
    // Stagger animation
    node.style.animationDelay = (i * 0.15) + 's';
    container.appendChild(node);
  });

  // Remove active class after animation
  setTimeout(() => {
    container.querySelectorAll('.proof-node').forEach(n => n.classList.remove('active'));
  }, 1500);
}

async function refresh() {
  try {
    const [diag, alertData, intentData, aiqStatus] = await Promise.all([
      fetchJSON('/diagnostics'),
      fetchJSON('/alerts'),
      fetchJSON('/intent-logs'),
      fetchJSON('/armoriq-status'),
    ]);
    updateStatus(diag);
    renderAlerts(alertData.alerts);
    renderIntentLogs(intentData.logs, aiqStatus);
  } catch (e) {
    console.error('Refresh failed', e);
  }
}

async function triggerHeal() {
  const btn = document.getElementById('heal-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Healing\u2026';
  try {
    const result = await fetchJSON('/auto-heal', { method: 'POST' });
    if (result.intent_verification) showProofChain(result.intent_verification);
    showBanner('info', '\ud83d\udd27 Auto-heal executed with intent verification');
    await refresh();
  } catch (e) { console.error('Heal failed', e); }
  btn.disabled = false;
  btn.innerHTML = '&#128295; Auto-Heal';
}

async function simulateFailure() {
  const btn = document.getElementById('sim-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Simulating\u2026';
  try {
    const result = await fetchJSON('/simulate-wifi-failure', { method: 'POST' });
    if (result.intent_verification) showProofChain(result.intent_verification);
    showBanner('resolved', '\u2705 WiFi failure simulated \u2192 auto-healed with ArmorIQ verification');
    await refresh();
  } catch (e) { console.error('Simulate failed', e); }
  btn.disabled = false;
  btn.innerHTML = '&#9889; Simulate Failure';
}

async function unsafeAction() {
  const btn = document.getElementById('unsafe-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Attempting\u2026';
  try {
    const result = await fetchJSON('/unsafe-action', { method: 'POST' });
    showBanner('blocked', '\ud83d\uded1 ACTION BLOCKED \u2014 ArmorIQ denied execution without intent token');
    await refresh();
  } catch (e) { console.error('Unsafe action failed', e); }
  btn.disabled = false;
  btn.innerHTML = '&#128274; Test Unsafe Action';
}

async function clearAll() {
  try {
    await Promise.all([
      fetchJSON('/alerts/clear', { method: 'POST' }),
      fetchJSON('/intent-logs/clear', { method: 'POST' }),
    ]);
    document.getElementById('proof-chain').style.display = 'none';
    document.getElementById('last-verified').classList.remove('visible');
    await refresh();
  } catch (e) { console.error('Clear failed', e); }
}

refresh();
setInterval(refresh, 6000);
</script>
</body>
</html>"""
