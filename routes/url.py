import os
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from services.url_service import (
    create_short_url,
    resolve_short_code,
    get_url_metadata,
    increment_clicks,
)
from db.database import get_db
from redis.asyncio import from_url as redis_from_url
from schemas.url_schemas import (
    UrlCreateRequest,
    UrlCreateResponse,
    UrlResponse,
    UrlMetadataResponse,
)
from services.exceptions import UrlExpiredError, ShortCodeNotFoundError

router = APIRouter(prefix="/url", tags=["URL Management"])
redirect_router = APIRouter(tags=["Redirects"])
limiter = Limiter(key_func=get_remote_address)
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not configured. Set REDIS_URL in environment.")
redis = redis_from_url(REDIS_URL)

@router.post("/create", response_model=UrlCreateResponse)
@limiter.limit(f"{os.getenv('RATE_LIMIT', '5/minute')} burst {os.getenv('RATE_LIMIT_BURST', '10')}")
async def create_url(
    request: Request,
    url_request: UrlCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> UrlCreateResponse:
    short_code = await create_short_url(
        long_url=str(url_request.original_url),
        db=db,
        redis=redis,
        user_id=None,
    )
    return UrlCreateResponse(short_code=short_code, long_url=url_request.original_url)

@router.get("/{short_code}", response_model=UrlMetadataResponse)
@limiter.limit(f"{os.getenv('RATE_LIMIT', '5/minute')} burst {os.getenv('RATE_LIMIT_BURST', '10')}")
async def get_metadata(
    request: Request,
    short_code: str,
    db: AsyncSession = Depends(get_db),
) -> UrlMetadataResponse:
    try:
        meta = await get_url_metadata(short_code=short_code, db=db, redis=redis)
        return UrlMetadataResponse(**meta)
    except UrlExpiredError:
        raise HTTPException(status_code=410, detail="URL has expired")
    except ShortCodeNotFoundError:
        raise HTTPException(status_code=404, detail="Short code not found")


@redirect_router.get("/r/{short_code}")
@limiter.limit(f"{os.getenv('RATE_LIMIT', '5/minute')} burst {os.getenv('RATE_LIMIT_BURST', '10')}")
async def redirect_short_code(
    request: Request,
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        long_url = await resolve_short_code(short_code=short_code, db=db, redis=redis)
        await increment_clicks(short_code=short_code, redis=redis, db=None)
        return RedirectResponse(url=long_url, status_code=302)
    except UrlExpiredError:
        raise HTTPException(status_code=410, detail="URL has expired")
    except ShortCodeNotFoundError:
        raise HTTPException(status_code=404, detail="Short code not found")

    








