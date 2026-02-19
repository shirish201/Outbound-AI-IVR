import logging
import logging.handlers
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.database import init_db, close_db

# Ensure directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Configure logging to both console and file
log_format = "%(asctime)s %(name)s %(levelname)s %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)

file_handler = logging.handlers.RotatingFileHandler(
    "logs/ivr.log", maxBytes=10_000_000, backupCount=5, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(log_format))
file_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)


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
