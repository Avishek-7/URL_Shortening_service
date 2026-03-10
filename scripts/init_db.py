import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text


# Ensure imports work when running as a script (e.g. /app/scripts/init_db.py)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def _wait_for_db(timeout_seconds: int = 60) -> None:
    start = asyncio.get_event_loop().time()

    # Import inside the loop so DATABASE_URL can be validated at runtime.
    from db.database import engine

    last_exc: Exception | None = None
    while True:
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if asyncio.get_event_loop().time() - start > timeout_seconds:
                raise RuntimeError(
                    "Database did not become ready in time"
                ) from last_exc
            await asyncio.sleep(2)


async def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not configured")

    await _wait_for_db(timeout_seconds=int(os.getenv("DB_INIT_TIMEOUT_SECONDS", "60")))

    from db.database import init_db

    await init_db()


if __name__ == "__main__":
    asyncio.run(main())
