from fastapi import APIRouter, Request
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from app.models import NotificationTypeEnum, NotificationStatusEnum
from app.services import NotificationService, TemplateService, PreferenceService

router = APIRouter(prefix="/api/v1", tags=["status"])
template_service = TemplateService()
preference_service = PreferenceService()
notification_service = NotificationService(template_service, preference_service)


@router.get("/notifications/{notification_id}")
async def get_notification_status(request: Request, notification_id: UUID):
    """Get notification status"""
    try:
        correlation_id = getattr(request.state, "correlation_id", None)

        notification = await notification_service.get_notification(notification_id)
        if not notification:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Notification not found: {notification_id}",
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                },
            }, 404

        response_data = {
            "id": str(notification.id),
            "notification_type": notification.notification_type.value,
            "status": notification.status.value,
            "channel_status": [
                {
                    "channel": cs.channel.value,
                    "status": cs.status.value,
                    "sent_at": cs.sent_at.isoformat() if cs.sent_at else None,
                    "delivered_at": cs.delivered_at.isoformat() if cs.delivered_at else None,
                    "provider_reference": cs.provider_reference,
                    "error_code": cs.error_code,
                    "error_message": cs.error_message,
                }
                for cs in notification.channel_status
            ],
            "recipient": notification.recipient.model_dump(),
            "created_at": notification.created_at.isoformat(),
            "queued_at": notification.queued_at.isoformat() if notification.queued_at else None,
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
            "delivered_at": notification.completed_at.isoformat() if notification.completed_at else None,
            "retry_count": notification.retry_count,
            "next_retry_at": notification.next_retry_at.isoformat() if notification.next_retry_at else None,
        }

        return {
            "success": True,
            "error": None,
            "data": response_data,
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


@router.get("/notifications")
async def list_notifications(
    request: Request,
    user_id: Optional[UUID] = None,
    notification_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List notifications with optional filtering"""
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

        # Convert string enums to enum objects
        notif_type = None
        if notification_type:
            try:
                notif_type = NotificationTypeEnum(notification_type)
            except ValueError:
                pass

        notif_status = None
        if status:
            try:
                notif_status = NotificationStatusEnum(status)
            except ValueError:
                pass

        notifications, total = await notification_service.list_notifications(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notif_type,
            status=notif_status,
            limit=limit,
            offset=offset,
        )

        notification_list = [
            {
                "id": str(n.id),
                "notification_type": n.notification_type.value,
                "status": n.status.value,
                "created_at": n.created_at.isoformat(),
                "queued_at": n.queued_at.isoformat() if n.queued_at else None,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
            }
            for n in notifications
        ]

        return {
            "success": True,
            "error": None,
            "data": {
                "notifications": notification_list,
                "total": total,
                "page": offset // limit if limit > 0 else 0,
                "page_size": limit,
            },
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
