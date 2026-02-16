import logging
from openai import AsyncOpenAI

from config.settings import settings
from src.core.models import CallOutcome

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

DEFAULT_SYSTEM_PROMPT = """You are a friendly, professional AI sales assistant making an outbound call.
Your goal is to qualify leads and determine interest level.

Guidelines:
- Be conversational and natural — not robotic
- Keep responses concise (1-3 sentences max) since this is a phone call
- Listen carefully and respond to what the person actually says
- If they're not interested, be polite and end the call gracefully
- If they're interested, gather relevant details and offer next steps
- Never be pushy or aggressive
"""


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def chat(messages: list[dict], system_prompt: str = "") -> str:
    """Send messages to OpenAI and return the assistant's reply."""
    client = _get_client()
    full_messages = [
        {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
        *messages,
    ]

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=full_messages,
        temperature=0.7,
        max_tokens=200,
    )
    reply = response.choices[0].message.content or ""
    logger.debug("LLM reply: %s", reply[:100])
    return reply


async def classify_outcome(transcript: str) -> CallOutcome:
    """Classify the call outcome from the transcript."""
    client = _get_client()

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify this call transcript into exactly ONE of these outcomes: "
                    "interested, not_interested, callback, voicemail, wrong_number, do_not_call. "
                    "Respond with ONLY the classification word, nothing else."
                ),
            },
            {"role": "user", "content": transcript},
        ],
        temperature=0,
        max_tokens=20,
    )
    raw = (response.choices[0].message.content or "unknown").strip().lower()

    try:
        return CallOutcome(raw)
    except ValueError:
        logger.warning("Unknown outcome classification: %s", raw)
        return CallOutcome.UNKNOWN


async def summarize(transcript: str) -> str:
    """Generate a one-paragraph summary of the call."""
    client = _get_client()

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": "Summarize this call transcript in 2-3 sentences. Focus on key points and outcome.",
            },
            {"role": "user", "content": transcript},
        ],
        temperature=0.3,
        max_tokens=150,
    )
    return (response.choices[0].message.content or "").strip()
