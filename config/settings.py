"""
config/settings.py
Centralized configuration, logging setup, and platform detection.
Includes ArmorIQ SDK config and demo-mode flag.
"""

import os
import sys
import logging

# ── Version ──────────────────────────────────────────────────────────────────
VERSION = "6.1.0"

# ── Runtime config (env-driven) ───────────────────────────────────────────────
# Render injects PORT; locally defaults to 3000
PORT    = int(os.environ.get("PORT", os.environ.get("VOLTIX_PORT", 3000)))
API_KEY = os.environ.get("VOLTIX_API_KEY", "mykey")
LOG_LVL = os.environ.get("VOLTIX_LOG_LEVEL", "INFO")

# ── Demo mode ─────────────────────────────────────────────────────────────────
DEMO_MODE = os.environ.get("VOLTIX_DEMO_MODE", "").lower() in ("true", "1", "yes")

# ── ArmorIQ SDK config ────────────────────────────────────────────────────────
ARMORIQ_API_KEY  = os.environ.get("ARMORIQ_API_KEY", "")
ARMORIQ_USER_ID  = os.environ.get("ARMORIQ_USER_ID", "voltix-agent-user")
ARMORIQ_AGENT_ID = os.environ.get("ARMORIQ_AGENT_ID", "voltix-mechanic-agent")
ARMORIQ_ENABLED  = bool(ARMORIQ_API_KEY)

# ── Platform flags ────────────────────────────────────────────────────────────
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS   = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LVL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("voltix")
