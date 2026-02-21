# ⚡ Voltix Mechanic Agent v6.1.0

**Autonomous self-healing infrastructure agent with ArmorIQ cryptographic intent verification**

Part of the Voltix / ArmorIQ ecosystem — autonomous device remediation for EV swap stations.

---

## 📁 Project Structure

```
SelfHealAgent/
├── config/
│   └── settings.py              # Configuration (env vars, logging, demo mode)
├── core/
│   ├── __init__.py
│   ├── alerts.py                # In-memory alert store & push logic
│   ├── diagnostics.py           # System diagnostic collection
│   ├── healer.py                # Auto-heal orchestrator (with ArmorIQ)
│   ├── intent_verification.py   # ArmorIQ SDK integration & audit logging
│   ├── monitor.py               # Background network monitor thread
│   └── simulator.py             # Failure simulation & demo mode engine
├── network/
│   ├── __init__.py
│   ├── base.py                  # Abstract network driver interface
│   ├── cloud_driver.py          # Cloud/Render simulated driver
│   ├── macos_driver.py          # macOS driver
│   └── windows_driver.py        # Windows driver (WinRT + netsh)
├── server/
│   ├── __init__.py
│   ├── handler.py               # HTTP handler (all endpoints)
│   └── dashboard.py             # Premium dashboard HTML
├── main.py                      # Entry point
├── requirements.txt             # Python dependencies
├── render.yaml                  # Render deployment blueprint
├── .env.example                 # Environment variables reference
└── README.md                    # This file
```

---

## 🚀 Quick Start (Local)

```powershell
# 1. Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1    # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Windows only) Install WinRT for real WiFi control
pip install winrt-runtime "winrt-Windows.Devices.Radios"

# 4. Set environment variables
$env:VOLTIX_API_KEY="mykey"

# 5. Run the agent (as Admin for WiFi control on Windows)
python main.py
```

Open **http://localhost:3000** for the live dashboard.

---

## ☁️ Deploy to Render

### Option A: Blueprint (recommended)

1. Push this repo to GitHub
2. Go to [dashboard.render.com](https://dashboard.render.com)
3. Click **New** → **Blueprint**
4. Connect your GitHub repo
5. Render auto-detects `render.yaml` and deploys

### Option B: Manual

1. **New** → **Web Service** → Connect GitHub repo
2. Settings:
   - **Runtime**: Python
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `python main.py`
3. Environment variables:

| Variable             | Value                     | Required |
|---------------------|---------------------------|----------|
| `VOLTIX_API_KEY`    | `mykey`                   | Yes      |
| `VOLTIX_DEMO_MODE`  | `true`                    | Yes (for demo) |
| `VOLTIX_LOG_LEVEL`  | `INFO`                    | No       |
| `ARMORIQ_API_KEY`   | *(your key or empty)*      | No       |
| `ARMORIQ_USER_ID`   | `voltix-agent-user`       | No       |
| `ARMORIQ_AGENT_ID`  | `voltix-mechanic-agent`   | No       |

> **Note:** Render injects `PORT` automatically. The agent binds to `0.0.0.0:$PORT`.

---

## ⚙️ Environment Variables

| Variable              | Default                   | Description                            |
|-----------------------|---------------------------|----------------------------------------|
| `PORT`                | `3000`                    | HTTP port (auto-set by Render)         |
| `VOLTIX_PORT`         | `3000`                    | HTTP port (local fallback)             |
| `VOLTIX_API_KEY`      | `mykey`                   | API authentication key                 |
| `VOLTIX_LOG_LEVEL`    | `INFO`                    | Logging level                          |
| `VOLTIX_DEMO_MODE`    | `false`                   | Auto-generate failures every 60-120s   |
| `ARMORIQ_API_KEY`     | *(empty)*                 | ArmorIQ SDK key (empty = simulation)   |
| `ARMORIQ_USER_ID`     | `voltix-agent-user`       | ArmorIQ composite identity             |
| `ARMORIQ_AGENT_ID`    | `voltix-mechanic-agent`   | ArmorIQ agent identity                 |

---

## 🏗️ Architecture

The agent follows a **detect → plan → verify → act → confirm** loop:

1. **Detect** — Background monitor polls WiFi/network state every 15s
2. **Plan** — ArmorIQ `capture_plan()` declares the intended action
3. **Verify** — `get_intent_token()` obtains a signed Ed25519 token
4. **Act** — Platform driver executes recovery (toggle WiFi, flush DNS, etc.)
5. **Confirm** — `invoke()` logs through ArmorIQ proxy with Merkle proof

On Linux/cloud (Render), the **CloudDriver** simulates WiFi hardware for demos.

---

## 🔗 API Endpoints

| Method | Path                       | Auth | Description                              |
|--------|---------------------------|------|------------------------------------------|
| GET    | `/`                        | No   | Dashboard UI                             |
| GET    | `/health`                  | No   | Health + ArmorIQ status + demo mode      |
| GET    | `/diagnostics`             | Yes  | Full system diagnostics                  |
| GET    | `/alerts`                  | Yes  | Alert history                            |
| GET    | `/adapter`                 | Yes  | Adapter info + state                     |
| GET    | `/intent-logs`             | Yes  | Intent verification audit log            |
| GET    | `/armoriq-status`          | Yes  | ArmorIQ SDK mode, counters, version      |
| POST   | `/auto-heal`               | Yes  | Trigger auto-heal with intent verification |
| POST   | `/simulate-wifi-failure`   | Yes  | **Demo:** force failure → auto-heal      |
| POST   | `/unsafe-action`           | Yes  | **Demo:** attempt action without token   |
| POST   | `/flush-dns`               | Yes  | Flush DNS cache                          |
| POST   | `/enable-wifi`             | Yes  | Enable WiFi adapter                      |
| POST   | `/restart-network`         | Yes  | Full network stack restart               |
| POST   | `/alerts/clear`            | Yes  | Clear alert history                      |
| POST   | `/intent-logs/clear`       | Yes  | Clear intent verification log            |

Authentication: `X-API-Key` header.

---

## 🎬 Hackathon Demo Script

1. Open the dashboard in your browser
2. Click **⚡ Simulate Failure** — watch:
   - Red "WiFi Disabled" alert appears
   - ArmorIQ proof chain animates: `capture_plan → get_intent_token → execute → invoke_verify`
   - Intent verification log populates with green ✅ VERIFIED badge
   - Status card recovers to green
3. Click **🔒 Test Unsafe Action** — watch:
   - Purple "BLOCKED" banner appears
   - Red 🛑 BLOCKED entry in intent log
   - Security enforcement logged
4. Repeat to show accumulating verification counter
5. Demo mode auto-generates failures if `VOLTIX_DEMO_MODE=true`

---

## 📊 Deployment Verification Checklist

After deploying to Render:

```bash
# 1. Health check
curl https://YOUR-APP.onrender.com/health

# 2. Simulate failure
curl -X POST https://YOUR-APP.onrender.com/simulate-wifi-failure \
  -H "X-API-Key: mykey"

# 3. Test security block
curl -X POST https://YOUR-APP.onrender.com/unsafe-action \
  -H "X-API-Key: mykey"

# 4. Check intent logs
curl https://YOUR-APP.onrender.com/intent-logs \
  -H "X-API-Key: mykey"

# 5. Open dashboard in browser
open https://YOUR-APP.onrender.com/
```

Expected results:
- `/health` returns `{"status": "ok", "version": "6.1.0", "armoriq_mode": "local_simulation", ...}`
- `/simulate-wifi-failure` returns simulation report with `intent_verification` block
- `/unsafe-action` returns `{"status": "blocked", ...}`
- Dashboard shows live updates, proof chain, and verification counters
