from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class CallStatus(str, Enum):
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    MACHINE = "machine"


class CallOutcome(str, Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CALLBACK = "callback"
    VOICEMAIL = "voicemail"
    NO_ANSWER = "no_answer"
    WRONG_NUMBER = "wrong_number"
    DO_NOT_CALL = "do_not_call"
    UNKNOWN = "unknown"


class CampaignStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Contact:
    name: str
    phone: str
    email: str = ""
    company: str = ""
    notes: str = ""
    row_number: int = 0  # Row in Google Sheet for writing results back


@dataclass
class CallRecord:
    id: str = ""
    campaign_id: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    twilio_call_sid: str = ""
    status: CallStatus = CallStatus.QUEUED
    outcome: CallOutcome = CallOutcome.UNKNOWN
    summary: str = ""
    transcript: str = ""
    duration_seconds: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Campaign:
    id: str = ""
    name: str = ""
    sheet_url: str = ""
    system_prompt: str = ""
    greeting: str = "Hi, this is an AI assistant calling on behalf of our team. Do you have a moment to chat?"
    status: CampaignStatus = CampaignStatus.CREATED
    total_contacts: int = 0
    completed_calls: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
