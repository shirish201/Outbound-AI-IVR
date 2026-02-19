# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Outbound AI IVR system — makes automated outbound phone calls using AI for real-time voice conversations. Reads contacts from Google Sheets, calls them via Twilio, conducts conversations using GPT-4o, and writes results back to the sheet.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (requires .env configured, see .env.example)
uvicorn src.main:app --reload

# The server needs a public URL for Twilio webhooks (e.g., ngrok)
```

No test suite or linter is configured yet.

## Architecture

### Audio Pipeline (real-time, per-call)

```
Twilio Media Stream (mulaw 8kHz WebSocket)
  → Deepgram STT (real-time transcription)
  → OpenAI GPT-4o (response generation)
  → ElevenLabs TTS (speech synthesis, Turbo v2.5)
  → Twilio Media Stream (mulaw 8kHz back to caller)
```

### Core Flow

1. **Campaign creation** — POST `/campaigns/` with name, Google Sheet URL, system prompt, greeting
2. **Campaign start** — POST `/campaigns/{id}/start` reads contacts from sheet, launches calls with `asyncio.Semaphore` concurrency control
3. **Twilio webhook** — POST `/twilio/voice` receives inbound call events, returns TwiML connecting to WebSocket
4. **WebSocket conversation** — `/twilio/stream/{call_record_id}` runs `ConversationManager` which orchestrates STT→LLM→TTS loop
5. **Call completion** — outcome classified by OpenAI, summary + transcript written back to Google Sheet

### Key Modules

- **`src/main.py`** — FastAPI app, mounts routers, initializes DB on startup
- **`src/core/conversation.py`** — `ConversationManager`: per-call state machine handling turn-taking, interruption detection (cancels TTS if human speaks 2+ words during AI speech), and transcript accumulation
- **`src/core/campaign.py`** — Campaign orchestration: concurrent call dispatch, polling for completion (3s intervals), Google Sheet result writeback
- **`src/services/`** — One module per external API (Twilio, Deepgram, OpenAI, ElevenLabs, Google Sheets). Singleton clients, all async
- **`src/db/`** — Async SQLite via aiosqlite, repository pattern
- **`config/settings.py`** — Pydantic `BaseSettings` loading from `.env`

### Data Model

Two SQLite tables: `campaigns` (id, name, sheet_url, system_prompt, greeting, status, counters) and `call_records` (id, campaign_id, contact info, twilio_call_sid, status, outcome, summary, transcript, duration).

Key enums in `src/core/models.py`: `CallStatus`, `CallOutcome`, `CampaignStatus`.

### External Service Dependencies

All require API keys in `.env`:
- **Twilio** — outbound calls, media streams, status callbacks, answering machine detection
- **Deepgram** — real-time STT via WebSocket
- **OpenAI** — conversation LLM + call outcome classification
- **ElevenLabs** — TTS synthesis
- **Google Sheets** (via gspread + service account) — contact source and result destination
