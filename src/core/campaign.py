import asyncio
import logging

from config.settings import settings
from src.core.models import Contact, CampaignStatus, CallStatus, CallOutcome
from src.db import repository
from src.services import twilio_service, sheets_service

logger = logging.getLogger(__name__)

# Active campaign tasks, keyed by campaign_id
active_campaigns: dict[str, asyncio.Task] = {}


async def start_campaign(campaign_id: str) -> None:
    """Launch a campaign — reads contacts, queues calls with concurrency control."""
    campaign = await repository.get_campaign(campaign_id)
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    if campaign_id in active_campaigns:
        raise ValueError(f"Campaign {campaign_id} is already running")

    task = asyncio.create_task(_run_campaign(campaign_id))
    active_campaigns[campaign_id] = task


async def stop_campaign(campaign_id: str) -> None:
    """Stop a running campaign."""
    task = active_campaigns.pop(campaign_id, None)
    if task:
        task.cancel()
        await repository.update_campaign_status(campaign_id, CampaignStatus.PAUSED)
        logger.info("Campaign %s stopped", campaign_id)


async def _run_campaign(campaign_id: str) -> None:
    """Main campaign loop — process contacts with concurrency semaphore."""
    try:
        campaign = await repository.get_campaign(campaign_id)
        if not campaign:
            return

        await repository.update_campaign_status(campaign_id, CampaignStatus.RUNNING)

        # Read contacts from Google Sheet
        contacts = await asyncio.to_thread(sheets_service.read_contacts, campaign.sheet_url)
        await repository.set_campaign_total(campaign_id, len(contacts))
        logger.info("Campaign %s: %d contacts loaded", campaign_id, len(contacts))

        # Process contacts with concurrency limit
        semaphore = asyncio.Semaphore(settings.max_concurrent_calls)
        tasks = [
            _process_contact(semaphore, campaign_id, campaign.sheet_url, contact)
            for contact in contacts
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        await repository.update_campaign_status(campaign_id, CampaignStatus.COMPLETED)
        logger.info("Campaign %s completed", campaign_id)

    except asyncio.CancelledError:
        logger.info("Campaign %s was cancelled", campaign_id)
    except Exception:
        logger.exception("Campaign %s failed", campaign_id)
        await repository.update_campaign_status(campaign_id, CampaignStatus.FAILED)
    finally:
        active_campaigns.pop(campaign_id, None)


async def _process_contact(
    semaphore: asyncio.Semaphore,
    campaign_id: str,
    sheet_url: str,
    contact: Contact,
) -> None:
    """Place a single call and wait for it to complete."""
    async with semaphore:
        logger.info("Calling %s (%s)", contact.name, contact.phone)

        # Create call record in DB
        record = await repository.create_call_record(
            campaign_id=campaign_id,
            contact_name=contact.name,
            contact_phone=contact.phone,
            contact_context=contact.context_summary,
        )

        try:
            # Initiate the Twilio call
            call_sid = await asyncio.to_thread(
                twilio_service.make_call, contact.phone, record.id
            )
            await repository.update_call_record(record.id, twilio_call_sid=call_sid)

            # Wait for the call to finish (poll status)
            await _wait_for_call_completion(record.id)

            # Write result back to Google Sheet
            updated_record = await _get_record(record.id)
            if updated_record and contact.row_number > 0:
                await asyncio.to_thread(
                    sheets_service.write_result,
                    sheet_url,
                    contact.row_number,
                    updated_record.outcome.value,
                    updated_record.summary,
                )

        except Exception:
            logger.exception("Error processing contact %s", contact.name)
            await repository.update_call_record(
                record.id, status=CallStatus.FAILED, outcome=CallOutcome.UNKNOWN
            )


async def _wait_for_call_completion(record_id: str, timeout: int = 0) -> None:
    """Poll the call record until it's no longer in progress."""
    if timeout <= 0:
        timeout = settings.call_timeout_seconds + 120  # Extra buffer

    elapsed = 0
    while elapsed < timeout:
        record = await _get_record(record_id)
        if record and record.status in (
            CallStatus.COMPLETED, CallStatus.FAILED,
            CallStatus.BUSY, CallStatus.NO_ANSWER,
        ):
            return
        await asyncio.sleep(3)
        elapsed += 3

    logger.warning("Call %s timed out after %ds", record_id, timeout)


async def _get_record(record_id: str):
    """Helper to fetch a call record by ID."""
    from src.db.database import get_db
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM call_records WHERE id = ?", (record_id,)
    )
    if not rows:
        return None
    from src.db.repository import _row_to_call_record
    return _row_to_call_record(rows[0])
