# pyright: reportGeneralTypeIssues=false
# pyright: reportFunctionMemberAccess=false

import json
import os
import ipaddress
from typing import Any, cast
from urllib.parse import urlsplit
from datetime import datetime, timedelta
import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.url import URL
from utils.encoder import encode_base62
from services.exceptions import (
    UrlExpiredError,
    ShortCodeNotFoundError,
    AliasAlreadyInUseError,
)

KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "short:")
CLICK_PREFIX = os.getenv("REDIS_CLICK_PREFIX", "url:clicks:")
META_PREFIX = os.getenv("REDIS_META_PREFIX", "url:meta:")


async def create_short_url(
    long_url: str,
    db: AsyncSession,
    redis,
    user_id: int | None = None,
    expire_in_days: int | None = None,
    custom_alias: str | None = None,
) -> str:
    long_url = _normalize_long_url(long_url)
    _reject_loopback_targets(long_url)

    existing_url_result = await db.execute(select(URL).where(URL.long_url == long_url))
    existing_url = existing_url_result.scalar_one_or_none()
    if existing_url:
        return cast(str, existing_url.short_code)

    alias = (custom_alias or "").strip() or None
    if alias:
        existing_alias_result = await db.execute(
            select(URL).where(URL.short_code == alias)
        )
        if existing_alias_result.scalar_one_or_none() is not None:
            raise AliasAlreadyInUseError()

    # short_code is NOT NULL in the DB. When no alias is provided, insert a
    # temporary unique value and overwrite it after we have the row id.
    temp_code = f"__tmp__{uuid.uuid4().hex}"
    new_url = URL(long_url=long_url, user_id=user_id, short_code=alias or temp_code)
    if expire_in_days:
        new_url.expires_at = datetime.utcnow() + timedelta(days=expire_in_days)  # type: ignore
    db.add(new_url)
    await db.flush()

    if alias:
        short_code = alias
    else:
        short_code = encode_base62(cast(int, new_url.id))
        new_url.short_code = short_code  # type: ignore

    await db.commit()
    await db.refresh(new_url)

    ttl = _ttl_seconds(new_url.expires_at)
    if ttl is None:
        await redis.set(_redis_key(short_code), long_url)
    elif ttl > 0:
        await redis.set(_redis_key(short_code), long_url, ex=ttl)
    await _cache_metadata(redis, new_url)
    return short_code


async def resolve_short_code(short_code: str, db: AsyncSession, redis) -> str:
    long_url = await redis.get(_redis_key(short_code))
    if long_url:
        # Rely solely on Redis TTL; do not query DB on cache hit
        return long_url.decode("utf-8")

    result = await db.execute(select(URL).where(URL.short_code == short_code))
    url_entry = result.scalar_one_or_none()
    if url_entry:
        if await is_expired(url_entry):
            await redis.delete(_redis_key(short_code))
            raise UrlExpiredError()
        ttl = _ttl_seconds(url_entry.expires_at)
        if ttl is None:
            await redis.set(_redis_key(short_code), url_entry.long_url)
        elif ttl > 0:
            await redis.set(_redis_key(short_code), url_entry.long_url, ex=ttl)
        await _cache_metadata(redis, url_entry)
        return cast(str, url_entry.long_url)
    raise ShortCodeNotFoundError()


async def increment_clicks(
    short_code: str, redis, db: AsyncSession | None = None
) -> None:
    await redis.incr(_clicks_key(short_code))
    return None


async def get_url_metadata(short_code: str, db: AsyncSession, redis) -> dict:
    cached_meta = await redis.get(_meta_key(short_code))
    cached_clicks = await redis.get(_clicks_key(short_code))
    pending_clicks = int(cached_clicks) if cached_clicks else 0
    if cached_meta:
        meta = json.loads(cached_meta)
        meta["clicks"] = meta.get("clicks", 0) + pending_clicks
        return meta

    result = await db.execute(select(URL).where(URL.short_code == short_code))
    url_entry = result.scalar_one_or_none()
    if url_entry:
        if await is_expired(url_entry):
            raise UrlExpiredError()
        await _cache_metadata(redis, url_entry)
        return {
            "long_url": url_entry.long_url,
            "short_code": url_entry.short_code,
            "clicks": url_entry.clicks + pending_clicks,
            "created_at": url_entry.created_at.isoformat()
            if url_entry.created_at
            else None,
            "expires_at": url_entry.expires_at.isoformat()
            if url_entry.expires_at
            else None,
        }
    raise ShortCodeNotFoundError()


async def is_expired(url_entry) -> bool:
    if url_entry.expires_at is not None and datetime.utcnow() > url_entry.expires_at:
        return True
    return False


def _ttl_seconds(expires_at) -> int | None:
    if expires_at is None:
        return None
    delta = (expires_at - datetime.utcnow()).total_seconds()
    return int(delta)


def _redis_key(short_code: str) -> str:
    return f"{KEY_PREFIX}{short_code}"


def _clicks_key(short_code: str) -> str:
    return f"{CLICK_PREFIX}{short_code}"


def _meta_key(short_code: str) -> str:
    return f"{META_PREFIX}{short_code}"


async def _cache_metadata(redis, url_entry: URL) -> None:
    payload = {
        "long_url": url_entry.long_url,
        "short_code": url_entry.short_code,
        "clicks": url_entry.clicks,
        "created_at": url_entry.created_at.isoformat()
        if url_entry.created_at
        else None,
        # Do not store expires_at in Redis; use key TTL only
        "user_id": url_entry.user_id,
    }
    ttl = _ttl_seconds(url_entry.expires_at)
    if ttl is None:
        await redis.set(_meta_key(cast(str, url_entry.short_code)), json.dumps(payload))
    elif ttl > 0:
        await redis.set(
            _meta_key(cast(str, url_entry.short_code)), json.dumps(payload), ex=ttl
        )


async def flush_click_counts(redis, db: AsyncSession) -> None:
    cursor = 0
    pending_updates: list[tuple[str, int]] = []
    while True:
        cursor, keys = await redis.scan(
            cursor=cursor, match=_clicks_key("*"), count=100
        )
        if keys:
            values = await redis.mget(keys)
            for key, value in zip(keys, values):
                if value is None:
                    continue
                key_str = (
                    key.decode("utf-8")
                    if isinstance(key, (bytes, bytearray))
                    else str(key)
                )
                short_code = key_str.removeprefix(CLICK_PREFIX)
                pending_updates.append((short_code, int(value)))
        if cursor == 0:
            break

    for short_code, delta in pending_updates:
        if delta <= 0:
            await redis.delete(_clicks_key(short_code))
            continue
        await db.execute(
            update(URL)
            .where(URL.short_code == short_code)
            .values(clicks=URL.clicks + delta)
        )
        await redis.delete(_clicks_key(short_code))

    if pending_updates:
        await db.commit()


async def flush_click_counts_async_task() -> None:
    # Import locally to avoid circular dependency at module import time.
    from services.tasks import flush_click_counts_task

    cast(Any, flush_click_counts_task).delay()


def _normalize_long_url(long_url: str) -> str:
    return (long_url or "").strip()


def _reject_loopback_targets(long_url: str) -> None:
    try:
        host = urlsplit(long_url).hostname
    except Exception:
        return

    if not host:
        return

    host_l = host.lower()
    if host_l == "localhost":
        raise ValueError(
            "localhost URLs are not allowed (use the server LAN IP/hostname)"
        )

    try:
        ip = ipaddress.ip_address(host_l)
        if ip.is_loopback or ip.is_unspecified:
            raise ValueError("loopback/unspecified IP URLs are not allowed")
    except ValueError as exc:
        # Not an IP literal, or explicitly rejected.
        if str(exc) in {"loopback/unspecified IP URLs are not allowed"}:
            raise
        return
