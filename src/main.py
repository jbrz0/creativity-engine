"""Main FastAPI application entry point."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.api import health, requests, status, feedback
from src.database.session import init_db, close_db
from src.utils.logging import setup_logging

# Initialize structured logging
setup_logging()
logger = structlog.get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Creativity Engine", version=app.version)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # TODO: Initialize Pinecone connection
    # TODO: Initialize Redis connection
    # TODO: Initialize RabbitMQ connection
    # TODO: Start background task processors

    yield

    # Cleanup
    logger.info("Shutting down Creativity Engine")
    await close_db()
    # TODO: Close other connections


# Create FastAPI application
app = FastAPI(
    title="Creativity Engine API",
    description="Advanced AI-powered creativity processing system with multi-agent architecture",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(requests.router, prefix="/api/v1", tags=["Requests"])
app.include_router(status.router, prefix="/api/v1", tags=["Status"])
app.include_router(feedback.router, prefix="/api/v1", tags=["Feedback"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Creativity Engine API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
