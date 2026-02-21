"""
core/alerts.py
Thread-safe in-memory alert store shared across the whole agent.
"""

import threading
import time
from datetime import datetime

from config.settings import log

_alerts: list = []
_lock = threading.Lock()
last_state: str = "unknown"


def push(level: str, title: str, message: str, state: str) -> dict:
    """Append an alert and return it. Thread-safe."""
    alert = {
        "id":        int(time.time() * 1000),
        "level":     level,
        "title":     title,
        "message":   message,
        "state":     state,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with _lock:
        _alerts.insert(0, alert)
        if len(_alerts) > 50:
            _alerts.pop()
    log.info(f"ALERT [{level.upper()}] {title}: {message}")
    return alert


def get_all() -> list:
    """Return a snapshot of all alerts."""
    with _lock:
        return list(_alerts)


def clear() -> None:
    """Clear the alert store."""
    with _lock:
        _alerts.clear()
