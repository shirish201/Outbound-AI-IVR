import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

from src.services.stt_service import STTSession
from src.services import llm_service, tts_service
from src.db import repository
from src.core.models import CallOutcome

logger = logging.getLogger(__name__)

# Shared state: keyed by call_record_id
active_conversations: dict[str, "ConversationManager"] = {}


class ConversationManager:
    """Orchestrates a single call: STT → LLM → TTS → Twilio."""

    def __init__(self, call_record_id: str, websocket: WebSocket):
        self.call_record_id = call_record_id
        self.websocket = websocket
        self.stream_sid: str = ""

        # Conversation state
        self.messages: list[dict] = []
        self.transcript_lines: list[str] = []
        self.system_prompt: str = ""
        self.greeting: str = ""

        # STT
        self._stt: STTSession | None = None
        self._interim_text: str = ""

        # TTS / speaking state
        self._tts_task: asyncio.Task | None = None
        self._is_speaking: bool = False

        # Utterance buffer — accumulate final transcripts until utterance end
        self._utterance_buffer: str = ""

    async def start(self) -> None:
        """Initialize the conversation — load campaign data, start STT."""
        # Load the call record to get campaign info
        record = None
        try:
            from src.db.database import get_db
            db = await get_db()
            rows = await db.execute_fetchall(
                "SELECT * FROM call_records WHERE id = ?", (self.call_record_id,)
            )
            if rows:
                campaign_id = rows[0]["campaign_id"]
                camp_rows = await db.execute_fetchall(
                    "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
                )
                if camp_rows:
                    self.system_prompt = camp_rows[0]["system_prompt"]
                    self.greeting = camp_rows[0]["greeting"]
        except Exception:
            logger.exception("Error loading campaign data")

        if not self.greeting:
            self.greeting = "Hi, this is an AI assistant. Do you have a moment to chat?"

        # Start STT session
        self._stt = STTSession(
            on_transcript=self._on_transcript,
            on_utterance_end=self._on_utterance_end,
        )
        await self._stt.start()
        logger.info("Conversation started: %s", self.call_record_id)

    async def stop(self) -> None:
        """Clean up: close STT, finalize call record."""
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()

        if self._stt:
            await self._stt.close()

        # Finalize — classify and summarize
        full_transcript = "\n".join(self.transcript_lines)
        if full_transcript.strip():
            try:
                outcome = await llm_service.classify_outcome(full_transcript)
                summary = await llm_service.summarize(full_transcript)
                await repository.update_call_record(
                    self.call_record_id,
                    outcome=outcome,
                    summary=summary,
                    transcript=full_transcript,
                )
                logger.info("Call finalized: %s outcome=%s", self.call_record_id, outcome.value)
            except Exception:
                logger.exception("Error finalizing call %s", self.call_record_id)

        # Increment campaign completed count
        try:
            from src.db.database import get_db
            db = await get_db()
            rows = await db.execute_fetchall(
                "SELECT campaign_id FROM call_records WHERE id = ?",
                (self.call_record_id,),
            )
            if rows:
                await repository.increment_completed_calls(rows[0]["campaign_id"])
        except Exception:
            logger.exception("Error incrementing completed calls")

    async def send_greeting(self) -> None:
        """Send the initial AI greeting after the stream connects."""
        self.messages.append({"role": "assistant", "content": self.greeting})
        self.transcript_lines.append(f"AI: {self.greeting}")
        await self._speak(self.greeting)

    async def receive_audio(self, audio_bytes: bytes) -> None:
        """Forward raw mulaw audio from Twilio to Deepgram STT."""
        if self._stt:
            await self._stt.send_audio(audio_bytes)

    # ── STT callbacks ──────────────────────────────────────

    async def _on_transcript(self, text: str, is_final: bool) -> None:
        """Called by Deepgram for each transcript result."""
        if not is_final:
            self._interim_text = text
            # Interruption: if human speaks while AI is talking, cancel TTS
            if self._is_speaking and len(text.split()) >= 2:
                logger.info("Interruption detected, cancelling TTS")
                await self._cancel_speech()
            return

        # Final transcript
        self._interim_text = ""
        if text.strip():
            self._utterance_buffer += (" " + text) if self._utterance_buffer else text
            logger.info("STT final: %s", text)

    async def _on_utterance_end(self) -> None:
        """Called when Deepgram detects end of an utterance — time to respond."""
        utterance = self._utterance_buffer.strip()
        self._utterance_buffer = ""

        if not utterance:
            return

        logger.info("Human said: %s", utterance)
        self.messages.append({"role": "user", "content": utterance})
        self.transcript_lines.append(f"Human: {utterance}")

        # Get LLM response
        try:
            reply = await llm_service.chat(self.messages, self.system_prompt)
            self.messages.append({"role": "assistant", "content": reply})
            self.transcript_lines.append(f"AI: {reply}")
            logger.info("AI reply: %s", reply)
            await self._speak(reply)
        except Exception:
            logger.exception("Error getting LLM response")

    # ── TTS + Twilio audio output ──────────────────────────

    async def _speak(self, text: str) -> None:
        """Synthesize text and stream audio to Twilio."""
        # Cancel any ongoing speech
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()

        self._tts_task = asyncio.create_task(self._stream_audio(text))

    async def _stream_audio(self, text: str) -> None:
        """Stream TTS audio chunks to Twilio via the WebSocket."""
        self._is_speaking = True
        try:
            async for chunk in tts_service.synthesize_streaming(text):
                if not self._is_speaking:
                    break  # Interrupted
                # Send audio to Twilio as base64-encoded media message
                payload = base64.b64encode(chunk).decode("ascii")
                media_message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload},
                }
                await self.websocket.send_text(json.dumps(media_message))
        except asyncio.CancelledError:
            logger.debug("TTS streaming cancelled")
        except Exception:
            logger.exception("Error streaming TTS audio")
        finally:
            self._is_speaking = False

    async def _cancel_speech(self) -> None:
        """Cancel ongoing TTS and send clear event to Twilio."""
        self._is_speaking = False
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()

        # Tell Twilio to clear its audio buffer
        if self.stream_sid:
            clear_message = {
                "event": "clear",
                "streamSid": self.stream_sid,
            }
            try:
                await self.websocket.send_text(json.dumps(clear_message))
            except Exception:
                logger.debug("Failed to send clear event")
