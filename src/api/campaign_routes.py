import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core import campaign as campaign_orchestrator
from src.db import repository
from src.core.models import CampaignStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    name: str
    sheet_url: str
    system_prompt: str = ""
    greeting: str = "Hi, this is an AI assistant calling on behalf of our team. Do you have a moment to chat?"


@router.post("/")
async def create_campaign(req: CreateCampaignRequest):
    """Create a new campaign."""
    campaign = await repository.create_campaign(
        name=req.name,
        sheet_url=req.sheet_url,
        system_prompt=req.system_prompt,
        greeting=req.greeting,
    )
    return asdict(campaign)


@router.get("/")
async def list_campaigns():
    """List all campaigns."""
    campaigns = await repository.list_campaigns()
    return [asdict(c) for c in campaigns]


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign details."""
    campaign = await repository.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return asdict(campaign)


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: str):
    """Start a campaign — begins dialing contacts."""
    campaign = await repository.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status == CampaignStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Campaign is already running")

    try:
        await campaign_orchestrator.start_campaign(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "started", "campaign_id": campaign_id}


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    """Stop a running campaign."""
    await campaign_orchestrator.stop_campaign(campaign_id)
    return {"status": "stopped", "campaign_id": campaign_id}


@router.get("/{campaign_id}/calls")
async def get_campaign_calls(campaign_id: str):
    """Get all call records for a campaign."""
    records = await repository.get_call_records_for_campaign(campaign_id)
    return [asdict(r) for r in records]
