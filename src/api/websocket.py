import asyncio
import base64
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.core.conversation import ConversationManager, active_conversations

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/twilio/stream/{call_record_id}")
async def twilio_media_stream(websocket: WebSocket, call_record_id: str):
    """Bidirectional WebSocket for Twilio Media Streams.

    Twilio sends JSON messages with audio payloads (base64 mulaw).
    We send back JSON messages with audio payloads to play to the caller.
    """
    await websocket.accept()
    logger.info("WebSocket connected: call_record_id=%s", call_record_id)

    conversation = ConversationManager(call_record_id, websocket)
    active_conversations[call_record_id] = conversation

    stream_sid: str = ""

    try:
        await conversation.start()

        async for raw_message in websocket.iter_text():
            message = json.loads(raw_message)
            event = message.get("event")

            if event == "start":
                stream_sid = message["start"]["streamSid"]
                conversation.stream_sid = stream_sid
                logger.info("Stream started: stream_sid=%s", stream_sid)
                # Send the greeting once the stream is ready
                asyncio.create_task(conversation.send_greeting())

            elif event == "media":
                # Decode base64 mulaw audio and feed to STT
                audio_bytes = base64.b64decode(message["media"]["payload"])
                await conversation.receive_audio(audio_bytes)

            elif event == "stop":
                logger.info("Stream stopped: call_record_id=%s", call_record_id)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: call_record_id=%s", call_record_id)
    except Exception:
        logger.exception("WebSocket error: call_record_id=%s", call_record_id)
    finally:
        await conversation.stop()
        active_conversations.pop(call_record_id, None)
        logger.info("Conversation cleaned up: call_record_id=%s", call_record_id)
