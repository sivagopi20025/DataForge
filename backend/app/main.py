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
            except Exception:
                logger.exception("analytics_aggregation_failed", extra={"request_id": request_id})

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
