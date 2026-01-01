import asyncio
import os

from celery import Celery
from dotenv import load_dotenv

from db.database import AsyncSessionLocal
from services.url_service import flush_click_counts
from redis.asyncio import from_url as redis_from_url

load_dotenv()

celery_app = Celery(
    "api_shortening_service",
    broker=os.getenv("CELERY_BROKER_URL"),
    backend=os.getenv("CELERY_RESULT_BACKEND"),
)

# Schedule Redis click flushes; configurable via FLUSH_CLICKS_INTERVAL_SECONDS
FLUSH_INTERVAL = int(os.getenv("FLUSH_CLICKS_INTERVAL_SECONDS", "60"))
celery_app.conf.beat_schedule = {
    "flush_click_counts": {
        "task": "flush_click_counts",
        "schedule": FLUSH_INTERVAL,
    }
}
celery_app.conf.timezone = os.getenv("CELERY_TIMEZONE", "UTC")


@celery_app.task(name="flush_click_counts")
def flush_click_counts_task() -> None:
    async def _flush() -> None:
        # Import models so SQLAlchemy metadata is populated before queries
        from models import url, user  # noqa: F401
        
        redis = redis_from_url(os.getenv("REDIS_URL"))
        async with AsyncSessionLocal() as session:
            await flush_click_counts(redis, session)
        if hasattr(redis, "close"):
            await redis.close()

    asyncio.run(_flush())
