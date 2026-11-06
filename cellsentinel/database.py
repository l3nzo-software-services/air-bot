"""
Database management and SQLAlchemy ORM lifecycle for CellSentinel.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from cellsentinel.config import settings

logger = logging.getLogger("cellsentinel.database")

# SQLite connection args for multi-threaded FastAPI concurrency
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for thread-safe database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> bool:
    """
    Initialize database schema, verify connectivity, and seed verified tower reference data.
    Returns True upon successful verification.
    """
    from cellsentinel.models import CellTowerCache, Device, Telemetry

    # Ensure parent directory exists for SQLite
    if settings.DATABASE_URL.startswith("sqlite:///"):
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        import os
        from pathlib import Path
        db_dir = Path(db_path).parent
        if not db_dir.exists():
            os.makedirs(db_dir, exist_ok=True)

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Verify connectivity
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1;")).scalar()
        if result != 1:
            raise RuntimeError("Database connectivity check failed.")

    # Seed verified reference cell towers if cache is empty
    with SessionLocal() as session:
        count = session.query(CellTowerCache).count()
        if count == 0 and settings.VERIFIED_TOWERS_FILE.exists():
            try:
                with open(settings.VERIFIED_TOWERS_FILE, "r", encoding="utf-8") as f:
                    towers = json.load(f)
                    now_utc = datetime.now(timezone.utc)
                    for t in towers:
                        cache_entry = CellTowerCache(
                            mcc=t["mcc"],
                            mnc=t["mnc"],
                            lac=t["lac"],
                            cell_id=t["cell_id"],
                            latitude=t["latitude"],
                            longitude=t["longitude"],
                            accuracy_radius=t.get("accuracy_radius"),
                            source="LOCAL_VERIFIED",
                            last_updated=now_utc
                        )
                        session.add(cache_entry)
                    session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"Could not load verified towers reference file: {e}")

    return True
