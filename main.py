import os
import pkgutil
import importlib
import pathlib

from fastapi import FastAPI, APIRouter
from sqlalchemy import text
from redis.asyncio import from_url as redis_from_url
from slowapi import Limiter
from slowapi.util import get_remote_address
from services.exceptions import UrlExpiredError, ShortCodeNotFoundError
from fastapi.responses import JSONResponse

from db.database import AsyncSessionLocal

# Import models to ensure they're registered with SQLAlchemy
from models import url as _, user as __  # noqa: F401

# Import limiter instance from routes.url to match decorators
from routes.url import limiter as route_limiter


def _include_all_routers(app: FastAPI) -> None:
    import routes

    package_path = pathlib.Path(routes.__file__).parent
    for mod in pkgutil.iter_modules([str(package_path)]):
        module = importlib.import_module(f"routes.{mod.name}")
        for name in dir(module):
            attr = getattr(module, name)
            if isinstance(attr, APIRouter):
                app.include_router(attr)


def create_app() -> FastAPI:
    # Fail fast on critical envs before importing route modules
    if not os.getenv("REDIS_URL"):
        raise RuntimeError("REDIS_URL is not configured. Set REDIS_URL in environment.")

    app = FastAPI(title="API Shortening Service")

    # Attach rate limiter to app state (required by slowapi)
    app.state.limiter = (
        route_limiter
        if isinstance(route_limiter, Limiter)
        else Limiter(key_func=get_remote_address)
    )

    # Include all routers from routes/* dynamically
    _include_all_routers(app)

    # Exception handlers mapping domain errors to HTTP responses
    @app.exception_handler(UrlExpiredError)
    async def expired_handler(_, __):
        return JSONResponse(status_code=410, content={"detail": "URL has expired"})

    @app.exception_handler(ShortCodeNotFoundError)
    async def not_found_handler(_, __):
        return JSONResponse(status_code=404, content={"detail": "Short code not found"})

    @app.get("/health")
    async def healthcheck():
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return JSONResponse(
                status_code=503,
                content={"ok": False, "redis": "missing", "db": "unknown"},
            )

        redis = redis_from_url(redis_url)
        redis_ok = False
        db_ok = False
        try:
            redis_ok = bool(await redis.ping())
        except Exception:
            redis_ok = False
        finally:
            if hasattr(redis, "close"):
                await redis.close()

        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False

        ok = redis_ok and db_ok
        status = 200 if ok else 503
        return JSONResponse(
            status_code=status,
            content={
                "ok": ok,
                "redis": "ok" if redis_ok else "error",
                "db": "ok" if db_ok else "error",
            },
        )

    return app


app = create_app()
