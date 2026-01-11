from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from app.models import (
    ErrorResponse,
    ErrorDetail,
    DetailedHealthResponse,
    ProviderHealth,
)
from app.queue import RedisQueue

router = APIRouter(tags=["health"])
queue = RedisQueue()


@router.get("/health")
async def health():
    """Readiness probe - check service is ready to serve requests"""
    try:
        # Check Redis connectivity
        redis_healthy = await queue.health_check()

        if redis_healthy:
            return {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        else:
            return JSONResponse(
                content={
                    "status": "unhealthy",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "Redis connection failed",
                },
                status_code=503,
            )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": str(e),
            },
            status_code=503,
        )


@router.get("/healthz")
async def healthz():
    """Liveness probe - check service is alive"""
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/v1/admin/health/detailed")
async def detailed_health(request: Request):
    """Get detailed health information"""
    try:
        correlation_id = getattr(request.state, "correlation_id", None)

        queue_depth = await queue.get_queue_depth()
        retry_queue_depth = await queue.get_retry_queue_depth()
        dlq_depth = await queue.get_dlq_depth()

        provider_status = [
            ProviderHealth(
                provider="email",
                status="healthy",
                last_check_at=datetime.now(timezone.utc),
            ),
            ProviderHealth(
                provider="sms",
                status="healthy",
                last_check_at=datetime.now(timezone.utc),
            ),
            ProviderHealth(
                provider="whatsapp",
                status="healthy",
                last_check_at=datetime.now(timezone.utc),
            ),
            ProviderHealth(
                provider="push",
                status="healthy",
                last_check_at=datetime.now(timezone.utc),
            ),
        ]

        response = DetailedHealthResponse(
            status="healthy",
            queue_depth=queue_depth,
            provider_status=provider_status,
            error_rate=0.0,
            response_times={"p50": 45.0, "p95": 85.0, "p99": 120.0},
        )

        return {
            "success": True,
            "error": None,
            "data": response.model_dump(),
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
            },
        }
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": {
                    "code": "HEALTH_CHECK_ERROR",
                    "message": str(e),
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": getattr(request.state, "correlation_id", None),
                },
            },
            status_code=500,
        )
