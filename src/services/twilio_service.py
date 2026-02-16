import logging
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

from config.settings import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_twilio_client() -> Client:
    global _client
    if _client is None:
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _client


def make_call(to: str, call_record_id: str) -> str:
    """Initiate an outbound call. Returns the Twilio Call SID."""
    client = get_twilio_client()
    call = client.calls.create(
        to=to,
        from_=settings.twilio_phone_number,
        url=f"{settings.base_url}/twilio/voice?call_record_id={call_record_id}",
        status_callback=f"{settings.base_url}/twilio/status",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
        machine_detection="Enable",
        machine_detection_timeout=5,
    )
    logger.info("Call initiated: SID=%s to=%s", call.sid, to)
    return call.sid


def generate_stream_twiml(call_record_id: str) -> str:
    """Generate TwiML that connects to our WebSocket media stream."""
    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(
        url=f"wss://{_extract_host(settings.base_url)}/twilio/stream/{call_record_id}",
    )
    stream.parameter(name="call_record_id", value=call_record_id)
    response.append(connect)
    return str(response)


def _extract_host(url: str) -> str:
    """Extract host from URL (strip protocol)."""
    return url.replace("https://", "").replace("http://", "").rstrip("/")
