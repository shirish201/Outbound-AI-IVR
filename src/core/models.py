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
    customer_id: str = ""
    age: str = ""
    income: str = ""
    nationality: str = ""
    tenure_months: str = ""
    transactions_last_month: str = ""
    spends_last_month: str = ""
    previous_products: str = ""
    is_cross_sale_target: str = ""
    prediction_score: str = ""
    shap_features: str = ""
    shap_values: str = ""
    trigger_cols: str = ""
    row_number: int = 0  # Row in Google Sheet for writing results back

    @property
    def context_summary(self) -> str:
        """Build a context string for the LLM about this contact."""
        parts = []
        if self.age:
            parts.append(f"Age: {self.age}")
        if self.income:
            parts.append(f"Income: {self.income}")
        if self.nationality:
            parts.append(f"Nationality: {self.nationality}")
        if self.tenure_months:
            parts.append(f"Customer for {self.tenure_months} months")
        if self.transactions_last_month:
            parts.append(f"Transactions last month: {self.transactions_last_month}")
        if self.spends_last_month:
            parts.append(f"Spends last month: {self.spends_last_month}")
        if self.previous_products:
            parts.append(f"Previous products: {self.previous_products}")
        if self.prediction_score:
            parts.append(f"Prediction score: {self.prediction_score}")
        if self.shap_features:
            parts.append(f"Key factors: {self.shap_features}")
        if self.trigger_cols:
            parts.append(f"Trigger columns: {self.trigger_cols}")
        return "; ".join(parts)


@dataclass
class CallRecord:
    id: str = ""
    campaign_id: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    contact_context: str = ""
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
