import aiosqlite
import logging

logger = logging.getLogger(__name__)

DB_PATH = "data/ivr.db"

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sheet_url TEXT NOT NULL,
            system_prompt TEXT NOT NULL DEFAULT '',
            greeting TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'created',
            total_contacts INTEGER NOT NULL DEFAULT 0,
            completed_calls INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS call_records (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            twilio_call_sid TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued',
            outcome TEXT NOT NULL DEFAULT 'unknown',
            summary TEXT DEFAULT '',
            transcript TEXT DEFAULT '',
            duration_seconds INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );

        CREATE INDEX IF NOT EXISTS idx_call_records_campaign
            ON call_records(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_call_records_call_sid
            ON call_records(twilio_call_sid);
    """)
    await _db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _db


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None
        logger.info("Database connection closed")
