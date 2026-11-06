"""
CellSentinel Runner.
Single-command launcher that initializes the SQLite database, verifies connectivity,
validates schema and indexes, and starts the Uvicorn web server.
"""

import sys
import uvicorn
from cellsentinel.config import settings
from cellsentinel.database import init_db


def main():
    print("=" * 75)
    print("📡 AIR BOT - Cellular Telemetry & Lost Device Recovery Engine")
    print("=" * 75)
    print(f"[*] Platform Version : {settings.APP_VERSION}")
    print(f"[*] Database URL     : {settings.DATABASE_URL}")

    # Step 1-3: Initialize SQLite database, verify connectivity, create tables & indexes
    print("[*] Initializing database and verifying connectivity...")
    try:
        init_db()
        print("[✓] SQLite database connected, verified, and indexed successfully.")
        print("[✓] Verified local reference cell-tower catalog loaded.")
    except Exception as e:
        print(f"[!] Database initialization failed: {e}")
        sys.exit(1)

    print(f"[✓] Serving interactive dashboard on http://{settings.HOST}:{settings.PORT}")
    print(f"[✓] OpenAPI Interactive Documentation on http://{settings.HOST}:{settings.PORT}/docs")
    print("=" * 75)

    uvicorn.run(
        "cellsentinel.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()

