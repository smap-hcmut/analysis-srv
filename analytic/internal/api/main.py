"""
FastAPI application setup and configuration.
Defines the main app, middleware, exception handlers, and route registration.
"""

import uuid
from datetime import datetime
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from core.config import settings
from core.logger import logger
from core.database import init_database, close_database, db_manager


# Create FastAPI application
app = FastAPI(
    title="Analytics Engine API",
    description="REST API for querying social media analytics data",
    version=settings.service_version,
    docs_url="/swagger/index.html",  # Swagger UI path
    redoc_url=None,                 # Disable ReDoc
    openapi_url="/openapi.json",    # OpenAPI spec path
    root_path=settings.api_root_path if settings.api_root_path else None  # Handle ingress prefix
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Analytics API service...")
    await init_database()
    logger.info("Analytics API service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Analytics API service...")
    await close_database()
    logger.info("Analytics API service stopped")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add request ID to each request for tracing."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log incoming requests and responses."""
    request_id = getattr(request.state, 'request_id', 'unknown')
    start_time = datetime.utcnow()
    
    # Log request
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )
    
    # Process request
    response = await call_next(request)
    
    # Log response
    duration = (datetime.utcnow() - start_time).total_seconds() * 1000
    logger.info(
        f"Response {request_id}: {response.status_code} "
        f"({duration:.1f}ms)"
    )
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for standardized error responses."""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    logger.error(f"Unhandled exception in request {request_id}: {exc}")
    logger.exception("Exception details:")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "SYS_001",
                "message": "Internal server error",
                "details": []
            },
            "meta": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "request_id": request_id,
                "version": settings.service_version
            }
        }
    )


# Health endpoints are now in health router


# Register API routes
from internal.api.routes import posts, summary, trends, keywords, alerts, errors, health
app.include_router(posts.router, tags=["posts"])
app.include_router(summary.router, tags=["summary"])
app.include_router(trends.router, tags=["trends"])
app.include_router(keywords.router, tags=["keywords"])
app.include_router(alerts.router, tags=["alerts"])
app.include_router(errors.router, tags=["errors"])
app.include_router(health.router, tags=["health"])


if __name__ == "__main__":
    # For development only
    uvicorn.run(app, host="0.0.0.0", port=8000)