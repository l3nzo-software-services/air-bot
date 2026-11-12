"""
AIR BOT Desktop Application Launcher.
Packaged for Windows Standalone Executable (.exe).
Automatically launches the local engine and opens the AIR BOT Control Dashboard.
"""

import sys
import os

# In PyInstaller windowed mode (console=False), sys.stdout and sys.stderr are None.
# Redirect them before any print() or logging/uvicorn initialization runs.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure project directory is in Python path for standalone launcher & pyinstaller
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import time
import webbrowser
import threading
import uvicorn

from cellsentinel.config import settings
from cellsentinel.database import init_db

def open_dashboard():
    time.sleep(1.2)
    url = f"http://localhost:{settings.PORT}"
    print(f"[*] Opening AIR BOT Desktop Interface: {url}")
    webbrowser.open(url)

def main():
    print("=" * 65)
    print("🤖 AIR BOT - Cellular Telemetry & Lost Device Recovery Sentinel")
    print("=" * 65)
    print("[*] Initializing local encrypted vault and base-station catalog...")
    
    try:
        init_db()
        print("[✓] AIR BOT Engine Initialized Successfully.")
    except Exception as e:
        print(f"[!] Initialization error: {e}")
        sys.exit(1)

    # Launch browser window in background thread
    threading.Thread(target=open_dashboard, daemon=True).start()

    # Start FastAPI Web Server
    from cellsentinel.main import app
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=settings.PORT,
        log_level="warning",
        log_config=None,
        use_colors=False,
    )

if __name__ == "__main__":
    main()

