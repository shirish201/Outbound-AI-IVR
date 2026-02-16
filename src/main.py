import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.database import init_db, close_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Ensure data/ directory exists for SQLite
os.makedirs("data", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("IVR system started")
    yield
    await close_db()
    logger.info("IVR system shut down")


app = FastAPI(title="Outbound AI IVR", lifespan=lifespan)


# Register routers
from src.api.twilio_routes import router as twilio_router
from src.api.campaign_routes import router as campaign_router
from src.api.websocket import router as ws_router

app.include_router(twilio_router)
app.include_router(campaign_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
