from fastapi import APIRouter, Request
from datetime import datetime, timezone
from uuid import UUID
from app.models import UserPreferenceRequest, UserPreferenceResponse
from app.services import PreferenceService

router = APIRouter(prefix="/api/v1", tags=["preferences"])
preference_service = PreferenceService()


@router.get("/users/{user_id}/preferences")
async def get_user_preferences(request: Request, user_id: UUID):
    """Get user notification preferences"""
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        correlation_id = getattr(request.state, "correlation_id", None)

        if not tenant_id:
            return {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing tenant_id in token",
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                },
            }, 401

        preferences = await preference_service.get_user_preferences(tenant_id, user_id)

        response = UserPreferenceResponse(
            user_id=preferences.user_id,
            opted_out_channels=preferences.opted_out_channels,
            opted_out_notification_types=preferences.opted_out_notification_types,
            global_opt_out=preferences.global_opt_out,
            notification_frequency=preferences.notification_frequency,
            preferred_contact_channel=preferences.preferred_contact_channel,
            updated_at=preferences.updated_at,
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
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e),
                "details": None,
            },
            "data": None,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": getattr(request.state, "correlation_id", None),
            },
        }, 500


@router.patch("/users/{user_id}/preferences")
async def update_user_preferences(request: Request, user_id: UUID, payload: UserPreferenceRequest):
    """Update user notification preferences"""
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        correlation_id = getattr(request.state, "correlation_id", None)

        if not tenant_id:
            return {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing tenant_id in token",
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                },
            }, 401

        preferences = await preference_service.update_user_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
            opted_out_channels=payload.opted_out_channels,
            opted_out_notification_types=payload.opted_out_notification_types,
            global_opt_out=payload.global_opt_out,
            notification_frequency=payload.notification_frequency,
        )

        response = UserPreferenceResponse(
            user_id=preferences.user_id,
            opted_out_channels=preferences.opted_out_channels,
            opted_out_notification_types=preferences.opted_out_notification_types,
            global_opt_out=preferences.global_opt_out,
            notification_frequency=preferences.notification_frequency,
            preferred_contact_channel=preferences.preferred_contact_channel,
            updated_at=preferences.updated_at,
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
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(e),
                "details": None,
            },
            "data": None,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": getattr(request.state, "correlation_id", None),
            },
        }, 500
