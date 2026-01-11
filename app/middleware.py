import uuid
import json
import logging
from typing import Callable, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware to extract/generate and propagate correlation IDs"""

    async def dispatch(self, request: Request, call_next: Callable):
        correlation_id = request.headers.get("X-Correlation-Id")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request state for access in handlers
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response


class JWTMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate JWT tokens"""

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip auth for health endpoints
        if request.url.path in ["/health", "/healthz", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Check if in testing mode
        from app.config import get_settings
        settings = get_settings()
        
        if settings.TESTING:
            # Bypass authentication in test mode with proper UUIDs
            request.state.user_id = uuid.UUID("12345678-1234-4567-a8a0-321f97f01f41")
            request.state.tenant_id = uuid.UUID("e0ab0899-c00a-4c42-a8a0-321f97f01f41")
            request.state.role = "user"
            request.state.token = "test-token"
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing Authorization header",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": getattr(request.state, "correlation_id", str(uuid.uuid4())),
                    },
                },
            )

        # Extract bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid Authorization header format",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": getattr(request.state, "correlation_id", str(uuid.uuid4())),
                    },
                },
            )

        token = parts[1]
        # Decode token (simplified for now, would use proper JWT validation)
        try:
            # Parse JWT (simplified)
            import json
            import base64
            payload = token.split(".")[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            request.state.user_id = decoded.get("user_id")
            request.state.tenant_id = decoded.get("tenant_id")
            request.state.role = decoded.get("role", "user")
            request.state.token = token
        except Exception as e:
            logger.warning(f"Failed to decode JWT: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid token",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": getattr(request.state, "correlation_id", str(uuid.uuid4())),
                    },
                },
            )

        response = await call_next(request)
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set request context for logging"""

    async def dispatch(self, request: Request, call_next: Callable):
        request.state.start_time = datetime.now(timezone.utc)
        response = await call_next(request)

        # Add response headers
        duration = (datetime.now(timezone.utc) - request.state.start_time).total_seconds()
        response.headers["X-Process-Time"] = str(duration)

        return response
