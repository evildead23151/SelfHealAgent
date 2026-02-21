"""
server/handler.py
HTTP request handler factory.
Returns a BaseHTTPRequestHandler subclass wired to the active driver.
Includes ArmorIQ intent verification endpoints and demo simulation.
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from config.settings import API_KEY, VERSION, DEMO_MODE, log
from core import alerts
from core.diagnostics import get_diagnostics
from core.healer import auto_heal
from core.intent_verification import (
    get_intent_logs, clear_intent_logs, get_armoriq_status,
)
from core.simulator import simulate_wifi_failure, unsafe_action_attempt
from server.dashboard import DASHBOARD_HTML


def make_handler(driver):
    """Factory — closes over `driver` and returns a configured Handler class."""

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, fmt, *args):
            log.info(f"HTTP {self.address_string()} \"{fmt % args}\"")

        # ── Helpers ──────────────────────────────────────────────────────────

        def _send_json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj, indent=2, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def _auth(self) -> bool:
            key = self.headers.get("X-API-Key", "")
            if key != API_KEY:
                self._send_json(401, {"error": "Unauthorized"})
                return False
            return True

        # ── CORS preflight ────────────────────────────────────────────────────

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "X-API-Key, Content-Type")
            self.end_headers()

        # ── GET routes ────────────────────────────────────────────────────────

        def do_GET(self):
            path = urlparse(self.path).path

            if path in ("/", "/dashboard"):
                html = DASHBOARD_HTML.replace("%%API_KEY%%", API_KEY)
                self._send_html(html)
                return

            if path == "/health":
                aiq = get_armoriq_status()
                self._send_json(200, {
                    "status":  "ok",
                    "version": VERSION,
                    "adapter": driver.get_adapter_name(),
                    "armoriq_mode": aiq["mode"],
                    "verification_count": aiq["total_verifications"],
                    "blocked_count": aiq["total_blocked"],
                    "demo_mode": DEMO_MODE,
                })
                return

            if not self._auth():
                return

            if path == "/diagnostics":
                self._send_json(200, get_diagnostics(driver))

            elif path == "/alerts":
                self._send_json(200, {
                    "alerts": alerts.get_all(),
                    "count":  len(alerts.get_all()),
                })

            elif path == "/adapter":
                self._send_json(200, {
                    "adapter": driver.get_adapter_name(),
                    "state":   driver.get_wifi_state(),
                })

            # ── ArmorIQ intent verification endpoints ──────────────────────

            elif path == "/intent-logs":
                self._send_json(200, {
                    "logs": get_intent_logs(),
                    "count": len(get_intent_logs()),
                })

            elif path == "/armoriq-status":
                self._send_json(200, get_armoriq_status())

            else:
                self._send_json(404, {"error": "Not found"})

        # ── POST routes ───────────────────────────────────────────────────────

        def do_POST(self):
            path = urlparse(self.path).path

            if not self._auth():
                return

            if path == "/auto-heal":
                self._send_json(200, auto_heal(driver))

            elif path == "/flush-dns":
                ok, out = driver.flush_dns()
                self._send_json(200, {"ok": ok, "output": out})

            elif path == "/enable-wifi":
                self._send_json(200, driver.enable_wifi())

            elif path == "/restart-network":
                self._send_json(200, driver.restart_network())

            elif path == "/alerts/clear":
                alerts.clear()
                self._send_json(200, {"cleared": True})

            elif path == "/intent-logs/clear":
                clear_intent_logs()
                self._send_json(200, {"cleared": True})

            # ── Demo / simulation endpoints ────────────────────────────────

            elif path == "/simulate-wifi-failure":
                self._send_json(200, simulate_wifi_failure(driver))

            elif path == "/unsafe-action":
                self._send_json(403, unsafe_action_attempt())

            else:
                self._send_json(404, {"error": "Not found"})

    return Handler
