from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from backend.app.analytics import AnalyticsAggregator
from backend.app.api.v1.routes import router as v1_router
from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging
from backend.app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.app_env.lower() == "production":
        if not settings.api_key:
            raise RuntimeError("DATAFORGE_API_KEY is required when APP_ENV=production")
        if not settings.cors_origins:
            raise RuntimeError("CORS_ORIGINS must include at least one exact https:// origin when APP_ENV=production")
        if "*" in settings.cors_origins:
            raise RuntimeError("CORS_ORIGINS cannot include '*' when APP_ENV=production")
        if not all(origin.startswith("https://") for origin in settings.cors_origins):
            raise RuntimeError("CORS_ORIGINS must use exact https:// origins when APP_ENV=production")
    configure_logging(settings.log_level)
    app = FastAPI(title="DataForge Backend", version="0.6.0")
    app.state.SessionLocal = SessionLocal
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = request_id
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            if request.url.scheme == "https" or get_settings().app_env.lower() == "production":
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            logger.info(
                "api_request",
                extra={
                    "request_id": request_id,
                    "endpoint": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            try:
                db = request.app.state.SessionLocal()
                try:
                    AnalyticsAggregator(db).record_api_request()
                finally:
                    db.close()
            except Exception as exc:
                logger.warning(
                    "analytics_aggregation_skipped",
                    extra={
                        "request_id": request_id,
                        "reason": exc.__class__.__name__,
                    },
                )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc), "code": "DATAFORGE_ERROR"})

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        content = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail), "code": "HTTP_ERROR"}
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("database_error")
        return JSONResponse(status_code=500, content={"error": "Database error", "code": "DATAFORGE_ERROR"})

    @app.exception_handler(Exception)
    async def generic_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return JSONResponse(status_code=500, content={"error": "Internal server error", "code": "DATAFORGE_ERROR"})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "dataforge"}

    app.include_router(v1_router)
    return app


app = create_app()
