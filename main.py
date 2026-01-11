import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import CorrelationIDMiddleware, JWTMiddleware, RequestContextMiddleware
from app.routes import health, notifications, templates, preferences, status
from utils import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Server: {settings.HOST}:{settings.PORT}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.SERVICE_NAME}")


# Create FastAPI app
app = FastAPI(
    title="Notification Service API",
    description="Multi-channel notification orchestration service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(RequestContextMiddleware)
app.add_middleware(JWTMiddleware)
app.add_middleware(CorrelationIDMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(health.router)
app.include_router(notifications.router)
app.include_router(templates.router)
app.include_router(preferences.router)
app.include_router(status.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.ENVIRONMENT == "development",
    )
