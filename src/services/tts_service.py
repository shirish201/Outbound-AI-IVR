import logging
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


async def synthesize(text: str) -> bytes:
    """Convert text to speech using ElevenLabs HTTP streaming.

    Returns raw ulaw 8kHz audio bytes — no conversion needed for Twilio.
    """
    url = ELEVENLABS_TTS_URL.format(voice_id=settings.elevenlabs_voice_id)

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
                "output_format": "ulaw_8000",
            },
        )
        response.raise_for_status()

        # Collect all chunks
        audio_data = response.content
        logger.debug("TTS synthesized %d bytes for: %s", len(audio_data), text[:50])
        return audio_data


async def synthesize_streaming(text: str):
    """Yield audio chunks as they arrive from ElevenLabs.

    Each chunk is raw ulaw 8kHz — ready to send to Twilio.
    """
    url = ELEVENLABS_TTS_URL.format(voice_id=settings.elevenlabs_voice_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
                "output_format": "ulaw_8000",
            },
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=8000):
                if chunk:
                    yield chunk
