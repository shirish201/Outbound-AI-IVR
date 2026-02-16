import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response

from src.services.twilio_service import generate_stream_twiml
from src.db import repository
from src.core.models import CallStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["twilio"])


@router.post("/voice")
async def voice_webhook(request: Request, call_record_id: str = ""):
    """Twilio requests TwiML when the call is answered.
    Returns a <Connect><Stream> to open a bidirectional WebSocket."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    answered_by = form.get("AnsweredBy", "human")

    logger.info("Voice webhook: call_record_id=%s call_sid=%s answered_by=%s",
                call_record_id, call_sid, answered_by)

    # Update the call record with the Twilio SID
    if call_record_id:
        await repository.update_call_record(
            call_record_id,
            twilio_call_sid=str(call_sid),
            status=CallStatus.IN_PROGRESS,
        )

    # If answering machine detected, hang up
    if answered_by in ("machine_start", "machine_end_beep", "machine_end_silence", "fax"):
        logger.info("Machine detected for call_record_id=%s, hanging up", call_record_id)
        if call_record_id:
            from src.core.models import CallOutcome
            await repository.update_call_record(
                call_record_id,
                status=CallStatus.COMPLETED,
                outcome=CallOutcome.VOICEMAIL,
            )
        return Response(content="<Response><Hangup/></Response>", media_type="application/xml")

    twiml = generate_stream_twiml(call_record_id)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def status_callback(
    CallSid: str = Form(""),
    CallStatus: str = Form(""),
    CallDuration: str = Form("0"),
    AnsweredBy: str = Form(""),
):
    """Twilio sends status updates here."""
    logger.info("Status callback: sid=%s status=%s duration=%s answered_by=%s",
                CallSid, CallStatus, CallDuration, AnsweredBy)

    if not CallSid:
        return {"ok": True}

    record = await repository.get_call_record_by_sid(CallSid)
    if not record:
        return {"ok": True}

    # Map Twilio status to our enum
    status_map = {
        "initiated": "queued",
        "ringing": "ringing",
        "in-progress": "in-progress",
        "completed": "completed",
        "busy": "busy",
        "no-answer": "no-answer",
        "canceled": "failed",
        "failed": "failed",
    }
    from src.core.models import CallStatus as CS
    mapped = status_map.get(CallStatus, "failed")
    await repository.update_call_record(
        record.id,
        status=CS(mapped),
        duration_seconds=int(CallDuration) if CallDuration else 0,
    )
    return {"ok": True}
