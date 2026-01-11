import uuid
from fastapi import APIRouter, Request, status, HTTPException
from datetime import datetime, timezone
from app.models import (
    NotificationSendRequest,
    NotificationBatchRequest,
    NotificationResponse,
    NotificationBatchResponse,
    NotificationStatusEnum,
)
from app.services import NotificationService, TemplateService, PreferenceService
from app.queue import RedisQueue

router = APIRouter(prefix="/api/v1", tags=["notifications"])
template_service = TemplateService()
preference_service = PreferenceService()
notification_service = NotificationService(template_service, preference_service)
queue = RedisQueue()


@router.post("/notifications/send", status_code=202)
async def send_notification(request: Request, payload: NotificationSendRequest):
    """Send a single notification"""
    try:
        correlation_id = getattr(request.state, "correlation_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)

        if not tenant_id or not user_id:
            return {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing tenant_id or user_id in token",
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                },
            }, 401

        # Check if recipient is provided
        if not payload.recipient.user_id and not payload.recipient.email:
            return {
                "success": False,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Recipient must have user_id or email",
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                },
            }, 400

        # Check if user is opted out
        recipient_user_id = payload.recipient.user_id or user_id
        for channel in payload.channels:
            is_opted_out = await preference_service.is_opted_out(
                tenant_id, recipient_user_id, channel, payload.notification_type
            )
            if is_opted_out:
                return {
                    "success": False,
                    "error": {
                        "code": "RECIPIENT_OPTED_OUT",
                        "message": f"Recipient opted out of {channel.value}",
                        "details": None,
                    },
                    "data": None,
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "correlation_id": correlation_id,
                    },
                }, 400

        # Create notification
        notification = await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=recipient_user_id,
            notification_type=payload.notification_type,
            recipient=payload.recipient,
            channels=payload.channels,
            template_id=payload.template_id,
            template_variables=payload.template_variables,
            priority=payload.priority,
            correlation_id=payload.correlation_id or correlation_id,
            send_at=payload.send_at,
        )

        # Enqueue notification
        await queue.enqueue(notification)

        return {
            "success": True,
            "error": None,
            "data": {
                "notification_id": str(notification.id),
                "status": notification.status.value,
                "metadata": {
                    "timestamp": notification.created_at.isoformat(),
                    "correlation_id": str(notification.correlation_id),
                    "channels_attempted": [c.value for c in notification.channels_requested],
                },
            },
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": correlation_id,
            },
        }

    except ValueError as e:
        return {
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": str(e),
                "details": None,
            },
            "data": None,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "correlation_id": getattr(request.state, "correlation_id", None),
            },
        }, 404
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


@router.post("/notifications/batch", status_code=202)
async def send_batch_notifications(request: Request, payload: NotificationBatchRequest):
    """Send batch notifications"""
    try:
        correlation_id = getattr(request.state, "correlation_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)
        user_id = getattr(request.state, "user_id", None)

        if not tenant_id or not user_id:
            return {
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing tenant_id or user_id in token",
                    "details": None,
                },
                "data": None,
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "correlation_id": correlation_id,
                },
            }, 401

        batch_id = uuid.uuid4()
        notification_ids = []
        queued_count = 0
        failed_count = 0

        for send_request in payload.notifications:
            try:
                # Merge common variables with notification-specific variables
                merged_variables = {
                    **payload.common_template_variables,
                    **send_request.template_variables,
                }
                send_request.template_variables = merged_variables

                # Create and enqueue notification
                notification = await notification_service.create_notification(
                    tenant_id=tenant_id,
                    user_id=send_request.recipient.user_id or user_id,
                    notification_type=send_request.notification_type,
                    recipient=send_request.recipient,
                    channels=send_request.channels,
                    template_id=send_request.template_id,
                    template_variables=merged_variables,
                    priority=send_request.priority,
                    correlation_id=send_request.correlation_id or correlation_id,
                    send_at=send_request.send_at,
                )

                await queue.enqueue(notification)
                notification_ids.append(str(notification.id))
                queued_count += 1
            except Exception as e:
                failed_count += 1

        overall_status = (
            NotificationStatusEnum.SENT
            if failed_count == 0
            else (
                NotificationStatusEnum.PARTIAL
                if queued_count > 0
                else NotificationStatusEnum.FAILED
            )
        )

        return {
            "success": True,
            "error": None,
            "data": {
                "batch_id": str(batch_id),
                "status": overall_status.value,
                "summary": {
                    "total": len(payload.notifications),
                    "queued": queued_count,
                    "failed": failed_count,
                },
                "notification_ids": notification_ids,
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
