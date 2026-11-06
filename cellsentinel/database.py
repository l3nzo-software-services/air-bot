"""
Database engine and SQLite persistence layer for CellSentinel.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Generator
from cellsentinel.config import settings


def get_db_path() -> str:
    """Return database file path."""
    return str(settings.BASE_DIR / settings.DATABASE_PATH)


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(get_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database() -> None:
    """Initialize database tables, indexes, and initial telecom cache."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Devices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                imei_hash TEXT PRIMARY KEY,
                device_model TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                owner_phone TEXT NOT NULL,
                owner_email TEXT NOT NULL,
                recovery_pin_hash TEXT,
                state TEXT NOT NULL CHECK(state IN ('SECURE', 'LOST', 'RECOVERED')),
                last_mcc INTEGER,
                last_mnc INTEGER,
                last_lac INTEGER,
                last_cid INTEGER,
                last_rssi REAL,
                last_latitude REAL,
                last_longitude REAL,
                last_accuracy REAL,
                last_seen_at TIMESTAMP,
                last_transport TEXT,
                sim_imsi_hash TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Telemetry logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_imei_hash TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transport TEXT NOT NULL CHECK(transport IN ('HTTPS', 'SMS_OUT_OF_BAND')),
                mcc INTEGER NOT NULL,
                mnc INTEGER NOT NULL,
                lac INTEGER NOT NULL,
                cid INTEGER NOT NULL,
                signal_strength REAL NOT NULL,
                carrier_name TEXT,
                radio_type TEXT DEFAULT 'LTE',
                timing_advance INTEGER,
                sim_status TEXT DEFAULT 'ACTIVE',
                sim_imsi_hash TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                accuracy_radius REAL NOT NULL,
                resolver_source TEXT NOT NULL,
                raw_payload TEXT,
                FOREIGN KEY (device_imei_hash) REFERENCES devices(imei_hash) ON DELETE CASCADE
            );
        """)

        # 3. Persistent cell tower cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cell_cache (
                mcc INTEGER NOT NULL,
                mnc INTEGER NOT NULL,
                lac INTEGER NOT NULL,
                cid INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                range_meters REAL NOT NULL,
                carrier TEXT,
                source TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                query_count INTEGER DEFAULT 1,
                PRIMARY KEY (mcc, mnc, lac, cid)
            );
        """)

        # 4. Incident timeline & audit events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incident_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_imei_hash TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('INFO', 'WARNING', 'CRITICAL')),
                details TEXT NOT NULL,
                FOREIGN KEY (device_imei_hash) REFERENCES devices(imei_hash) ON DELETE CASCADE
            );
        """)

        # Indexes for fast querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_device ON telemetry_logs(device_imei_hash, timestamp DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_tower ON telemetry_logs(mcc, mnc, lac, cid);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_device ON incident_events(device_imei_hash, timestamp DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_state ON devices(state);")
