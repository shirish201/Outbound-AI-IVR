import asyncio
import logging
from typing import Callable, Awaitable

from deepgram import AsyncDeepgramClient
from deepgram.extensions.types.sockets.listen_v1_results_event import ListenV1ResultsEvent
from deepgram.extensions.types.sockets.listen_v1_utterance_end_event import ListenV1UtteranceEndEvent

from config.settings import settings

logger = logging.getLogger(__name__)


class STTSession:
    """Per-call Deepgram live transcription session using SDK v5."""

    def __init__(
        self,
        on_transcript: Callable[[str, bool], Awaitable[None]],
        on_utterance_end: Callable[[], Awaitable[None]] | None = None,
    ):
        """
        on_transcript(text, is_final) — called for each transcript result.
        on_utterance_end() — called when Deepgram detects end of speech.
        """
        self._on_transcript = on_transcript
        self._on_utterance_end = on_utterance_end
        self._client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)
        self._socket = None
        self._socket_ctx = None
        self._recv_task: asyncio.Task | None = None
        self._closed = False

    async def start(self) -> None:
        # v1.connect returns an async context manager yielding AsyncV1SocketClient
        self._socket_ctx = self._client.listen.v1.connect(
            model="nova-2",
            language="en-US",
            encoding="mulaw",
            sample_rate="8000",
            channels="1",
            punctuate="true",
            interim_results="true",
            utterance_end_ms="1200",
            vad_events="true",
            endpointing="300",
        )
        self._socket = await self._socket_ctx.__aenter__()

        # Start background task to receive events
        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info("Deepgram STT session started")

    async def send_audio(self, audio_bytes: bytes) -> None:
        if self._socket and not self._closed:
            await self._socket.send_media(audio_bytes)

    async def close(self) -> None:
        self._closed = True
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._socket_ctx:
            try:
                await self._socket_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._socket = None
            self._socket_ctx = None
        logger.info("Deepgram STT session closed")

    async def _recv_loop(self) -> None:
        """Background loop receiving events from Deepgram."""
        try:
            while not self._closed and self._socket:
                try:
                    event = await self._socket.recv()
                except Exception:
                    if self._closed:
                        break
                    logger.exception("Error receiving from Deepgram")
                    break

                if isinstance(event, ListenV1ResultsEvent):
                    await self._handle_results(event)
                elif isinstance(event, ListenV1UtteranceEndEvent):
                    if self._on_utterance_end:
                        await self._on_utterance_end()
        except asyncio.CancelledError:
            pass
        except Exception:
            if not self._closed:
                logger.exception("Deepgram recv loop error")

    async def _handle_results(self, event: ListenV1ResultsEvent) -> None:
        try:
            channel = event.channel
            if not channel or not channel.alternatives:
                return
            transcript = channel.alternatives[0].transcript
            if not transcript:
                return
            is_final = event.is_final
            await self._on_transcript(transcript, is_final)
        except Exception:
            logger.exception("Error handling transcript event")
