import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.library import router as library_router
from app.api.search import router as search_router
from app.api.videos import router as videos_router
from app.config import get_settings
from app.db import engine
from app.errors import AppError
from app.logging_config import configure_logging

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    if settings.public_deployment and not settings.api_token:
        raise RuntimeError("CLIPIT_PUBLIC_DEPLOYMENT=true requires CLIPIT_API_TOKEN. Refusing to start.")
    if settings.auth_mode == "local" and not settings.public_deployment:
        log.warning("Local single-user mode is on. Do not expose this API to the internet.")
    yield


def require_access(request: Request) -> None:
    settings = get_settings()
    protected = settings.public_deployment or settings.auth_mode == "token"
    if not protected:
        return
    if not settings.api_token:
        raise AppError(503, "auth_misconfigured", "Token authentication is on, but CLIPIT_API_TOKEN is empty.")
    if request.headers.get("authorization") != f"Bearer {settings.api_token}":
        raise AppError(401, "unauthorized", "Send a bearer token. This deployment does not allow anonymous access.")


app = FastAPI(title="Clip-It", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": "The request is missing a required field or has an invalid value."}},
    )


@app.get("/api/health")
def health():
    database = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database = "unavailable"
    redis_status = "unavailable"
    try:
        import redis

        client = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=0.3)
        client.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "unavailable"
    code = 200 if database == "ok" else 503
    return JSONResponse(
        status_code=code,
        content={
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "redis": redis_status,
            "auth_mode": get_settings().auth_mode,
            "public_deployment": get_settings().public_deployment,
        },
    )


protected = [Depends(require_access)]
app.include_router(videos_router, dependencies=protected)
app.include_router(search_router, dependencies=protected)
app.include_router(library_router, dependencies=protected)
