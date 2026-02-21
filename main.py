"""
Voltix Mechanic Agent v6.1.0
Entry point — detects platform, loads correct driver, starts monitor,
launches HTTP server. Cloud-ready (Render/Docker) and hackathon-demo ready.

Now with:
  - ArmorIQ SDK cryptographic intent verification
  - Cloud driver for non-Windows deployment
  - Demo mode for auto-generated failures

USAGE:
  # Local (Windows Admin PowerShell):
    $env:VOLTIX_API_KEY="mykey"
    python main.py

  # Cloud / Render:
    PORT=10000  (injected by Render)
    VOLTIX_API_KEY=mykey
    VOLTIX_DEMO_MODE=true
    python main.py
"""

from http.server import HTTPServer

from config.settings import (
    PORT, API_KEY, VERSION, IS_WINDOWS, IS_MACOS, IS_LINUX,
    ARMORIQ_ENABLED, ARMORIQ_API_KEY, DEMO_MODE, log,
)
from core.monitor import start_monitor
from core.simulator import start_demo_mode
from server.handler import make_handler


def _get_driver():
    """Return the platform-appropriate NetworkDriver instance."""
    if IS_WINDOWS:
        from network.windows_driver import WindowsDriver
        return WindowsDriver()
    elif IS_MACOS:
        from network.macos_driver import MacOSDriver
        return MacOSDriver()
    else:
        # Linux / Cloud / Docker / Render — use simulated cloud driver
        from network.cloud_driver import CloudDriver
        log.info("Linux/Cloud detected — using CloudDriver (simulated WiFi)")
        return CloudDriver()


def _check_admin():
    """Warn if not running with elevated privileges (Windows only)."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False
    if not is_admin:
        log.warning("=" * 60)
        log.warning("NOT running as Administrator!")
        log.warning("WiFi healing WILL NOT WORK without admin privileges.")
        log.warning("Right-click PowerShell -> Run as Administrator")
        log.warning("=" * 60)
    else:
        log.info("Running as Administrator ✓")


def _check_winrt():
    """Verify the WinRT radio package is installed (Windows only)."""
    if not IS_WINDOWS:
        return
    try:
        from winrt.windows.devices.radios import Radio, RadioState, RadioKind  # noqa: F401
        log.info("winrt-Windows.Devices.Radios is installed ✓")
    except ImportError:
        log.warning("=" * 60)
        log.warning("winrt-Windows.Devices.Radios is NOT installed!")
        log.warning("WiFi radio toggle will NOT work without it.")
        log.warning('Run: python -m pip install winrt-runtime "winrt-Windows.Devices.Radios"')
        log.warning("=" * 60)


def _check_armoriq():
    """Check ArmorIQ SDK status."""
    try:
        import armoriq_sdk  # noqa: F401
        log.info(f"armoriq-sdk v{armoriq_sdk.__version__} is installed ✓")
    except ImportError:
        log.warning("armoriq-sdk NOT installed. Run: python -m pip install armoriq-sdk")

    if ARMORIQ_ENABLED:
        log.info(f"ArmorIQ PRODUCTION mode (key: {ARMORIQ_API_KEY[:8]}...)")
    else:
        log.info("ArmorIQ LOCAL SIMULATION mode (set ARMORIQ_API_KEY for production)")


def main():
    log.info(f"╔══════════════════════════════════════════════╗")
    log.info(f"║  Voltix Mechanic Agent {VERSION:>8}              ║")
    log.info(f"║  ArmorIQ Intent Verification Engine          ║")
    log.info(f"╚══════════════════════════════════════════════╝")

    _check_admin()
    _check_winrt()
    _check_armoriq()

    driver = _get_driver()
    adapter = driver.get_adapter_name()
    log.info(f"Detected adapter: '{adapter}'")

    start_monitor(driver)

    # Start demo mode if enabled
    if DEMO_MODE:
        log.info("=" * 60)
        log.info("  DEMO MODE ACTIVE — auto-generating failures every 60-120s")
        log.info("=" * 60)
        start_demo_mode(driver)

    Handler = make_handler(driver)
    log.info(f"Binding to 0.0.0.0:{PORT}")
    log.info(f"Adapter: {adapter}  |  API key: {'set' if API_KEY else 'NOT SET'}")
    log.info(f"Demo mode: {'ON' if DEMO_MODE else 'OFF'}")
    log.info(f">>> Dashboard: http://localhost:{PORT}/")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
