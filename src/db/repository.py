import uuid
from datetime import datetime

from src.core.models import Campaign, CampaignStatus, CallRecord, CallStatus, CallOutcome
from src.db.database import get_db


# ── Campaigns ──────────────────────────────────────────────

async def create_campaign(name: str, sheet_url: str, system_prompt: str, greeting: str) -> Campaign:
    db = await get_db()
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=name,
        sheet_url=sheet_url,
        system_prompt=system_prompt,
        greeting=greeting,
        created_at=datetime.utcnow().isoformat(),
    )
    await db.execute(
        """INSERT INTO campaigns (id, name, sheet_url, system_prompt, greeting, status, total_contacts, completed_calls, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (campaign.id, campaign.name, campaign.sheet_url, campaign.system_prompt,
         campaign.greeting, campaign.status.value, campaign.total_contacts,
         campaign.completed_calls, campaign.created_at),
    )
    await db.commit()
    return campaign


async def get_campaign(campaign_id: str) -> Campaign | None:
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    )
    if not row:
        return None
    return _row_to_campaign(row[0])


async def list_campaigns() -> list[Campaign]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM campaigns ORDER BY created_at DESC")
    return [_row_to_campaign(r) for r in rows]


async def update_campaign_status(campaign_id: str, status: CampaignStatus) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE campaigns SET status = ? WHERE id = ?",
        (status.value, campaign_id),
    )
    await db.commit()


async def increment_completed_calls(campaign_id: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE campaigns SET completed_calls = completed_calls + 1 WHERE id = ?",
        (campaign_id,),
    )
    await db.commit()


async def set_campaign_total(campaign_id: str, total: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE campaigns SET total_contacts = ? WHERE id = ?",
        (total, campaign_id),
    )
    await db.commit()


# ── Call Records ───────────────────────────────────────────

async def create_call_record(campaign_id: str, contact_name: str, contact_phone: str) -> CallRecord:
    db = await get_db()
    now = datetime.utcnow().isoformat()
    record = CallRecord(
        id=str(uuid.uuid4()),
        campaign_id=campaign_id,
        contact_name=contact_name,
        contact_phone=contact_phone,
        created_at=now,
        updated_at=now,
    )
    await db.execute(
        """INSERT INTO call_records
           (id, campaign_id, contact_name, contact_phone, twilio_call_sid,
            status, outcome, summary, transcript, duration_seconds, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (record.id, record.campaign_id, record.contact_name, record.contact_phone,
         record.twilio_call_sid, record.status.value, record.outcome.value,
         record.summary, record.transcript, record.duration_seconds,
         record.created_at, record.updated_at),
    )
    await db.commit()
    return record


async def update_call_record(
    record_id: str,
    *,
    twilio_call_sid: str | None = None,
    status: CallStatus | None = None,
    outcome: CallOutcome | None = None,
    summary: str | None = None,
    transcript: str | None = None,
    duration_seconds: int | None = None,
) -> None:
    db = await get_db()
    updates: list[str] = []
    values: list = []
    if twilio_call_sid is not None:
        updates.append("twilio_call_sid = ?")
        values.append(twilio_call_sid)
    if status is not None:
        updates.append("status = ?")
        values.append(status.value)
    if outcome is not None:
        updates.append("outcome = ?")
        values.append(outcome.value)
    if summary is not None:
        updates.append("summary = ?")
        values.append(summary)
    if transcript is not None:
        updates.append("transcript = ?")
        values.append(transcript)
    if duration_seconds is not None:
        updates.append("duration_seconds = ?")
        values.append(duration_seconds)
    if not updates:
        return
    updates.append("updated_at = ?")
    values.append(datetime.utcnow().isoformat())
    values.append(record_id)
    await db.execute(
        f"UPDATE call_records SET {', '.join(updates)} WHERE id = ?", values
    )
    await db.commit()


async def get_call_record_by_sid(call_sid: str) -> CallRecord | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM call_records WHERE twilio_call_sid = ?", (call_sid,)
    )
    if not rows:
        return None
    return _row_to_call_record(rows[0])


async def get_call_records_for_campaign(campaign_id: str) -> list[CallRecord]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM call_records WHERE campaign_id = ? ORDER BY created_at", (campaign_id,)
    )
    return [_row_to_call_record(r) for r in rows]


# ── Row mappers ────────────────────────────────────────────

def _row_to_campaign(row) -> Campaign:
    return Campaign(
        id=row["id"],
        name=row["name"],
        sheet_url=row["sheet_url"],
        system_prompt=row["system_prompt"],
        greeting=row["greeting"],
        status=CampaignStatus(row["status"]),
        total_contacts=row["total_contacts"],
        completed_calls=row["completed_calls"],
        created_at=row["created_at"],
    )


def _row_to_call_record(row) -> CallRecord:
    return CallRecord(
        id=row["id"],
        campaign_id=row["campaign_id"],
        contact_name=row["contact_name"],
        contact_phone=row["contact_phone"],
        twilio_call_sid=row["twilio_call_sid"],
        status=CallStatus(row["status"]),
        outcome=CallOutcome(row["outcome"]),
        summary=row["summary"],
        transcript=row["transcript"],
        duration_seconds=row["duration_seconds"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
