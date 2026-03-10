from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeRedis


@pytest.fixture(scope="session", autouse=True)
def _test_env() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="shortly_tests_"))
    db_path = tmpdir / "test.sqlite3"

    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    os.environ.setdefault("REDIS_URL", "redis://fake")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://fake/1")
    os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://fake/2")
    os.environ.setdefault("RATE_LIMIT", "10000/minute")
    os.environ.setdefault("RATE_LIMIT_BURST", "10000")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Import after env vars are set.
    import main as main_mod
    import routes.url as routes_url
    from db.database import Base, engine

    # Reset DB for isolation.
    async def _reset() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())

    fake = FakeRedis()
    monkeypatch.setattr(routes_url, "redis", fake, raising=True)
    monkeypatch.setattr(main_mod, "redis_from_url", lambda _: fake, raising=True)

    return TestClient(main_mod.app)
