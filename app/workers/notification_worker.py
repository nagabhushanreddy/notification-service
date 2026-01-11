import asyncio
import logging
from app.queue import RedisQueue
from app.services import NotificationService, TemplateService, PreferenceService
from app.providers import EmailProvider, SMSProvider, WhatsAppProvider, PushProvider
from app.models import ChannelEnum, NotificationStatusEnum, ChannelStatus
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Initialize services
template_service = TemplateService()
preference_service = PreferenceService()
notification_service = NotificationService(template_service, preference_service)

# Initialize providers
providers = {
    ChannelEnum.EMAIL: EmailProvider(),
    ChannelEnum.SMS: SMSProvider(),
    ChannelEnum.WHATSAPP: WhatsAppProvider(),
    ChannelEnum.PUSH: PushProvider(),
}


async def start_notification_worker(queue: RedisQueue):
    """Background worker that processes notifications from queue"""
    logger.info("Notification worker started")

    while True:
        try:
            # Dequeue notifications
            notifications = await queue.dequeue(batch_size=10)

            if not notifications:
                # No notifications in queue, wait before checking again
                await asyncio.sleep(5)
                continue

            # Process each notification
            for notification_data in notifications:
                try:
                    await process_notification(queue, notification_data)
                except Exception as e:
                    logger.error(f"Error processing notification: {e}")

        except asyncio.CancelledError:
            logger.info("Notification worker cancelled")
            break
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            await asyncio.sleep(5)


async def process_notification(queue: RedisQueue, notification_data: dict):
    """Process a single notification"""
    notification_id = notification_data.get("id")
    tenant_id = notification_data.get("tenant_id")
    user_id = notification_data.get("user_id")
    channels_requested = notification_data.get("channels_requested", [])
    template_id = notification_data.get("template_id")
    template_variables = notification_data.get("template_variables", {})
    recipient = notification_data.get("recipient", {})

    logger.info(f"Processing notification: {notification_id}")

    try:
        # Get notification from storage
        from app.services.core_services import NOTIFICATIONS_STORE
        from uuid import UUID

        notification = NOTIFICATIONS_STORE.get(notification_id)
        if not notification:
            logger.warning(f"Notification not found in storage: {notification_id}")
            return

        # Update status to processing
        notification.status = NotificationStatusEnum.PROCESSING
        notification.processing_started_at = datetime.now(timezone.utc)

        # Get template
        template = await template_service.get_template(UUID(template_id))
        if not template:
            logger.error(f"Template not found: {template_id}")
            notification.status = NotificationStatusEnum.FAILED
            return

        # Track channel results
        channel_results = []
        success_count = 0

        # Send through each requested channel
        for channel_value in channels_requested:
            from app.models import ChannelEnum as ChannelEnumClass

            channel = ChannelEnumClass(channel_value)
            provider = providers.get(channel)

            if not provider:
                logger.warning(f"No provider for channel: {channel}")
                channel_results.append(
                    ChannelStatus(
                        channel=channel,
                        status=NotificationStatusEnum.FAILED,
                        error_code="PROVIDER_NOT_FOUND",
                        error_message=f"No provider configured for {channel}",
                    )
                )
                continue

            try:
                # Render template content
                rendered_content = await template_service.render_template(
                    template, channel, template_variables
                )

                # Get recipient contact info
                contact_info = recipient.get("email") or recipient.get("phone") or "user"

                # Send notification
                result = await provider.send(
                    recipient=contact_info,
                    subject=rendered_content.get("subject"),
                    body=rendered_content.get("body_html") or rendered_content.get("content"),
                    template_variables=template_variables,
                )

                if result.get("success"):
                    success_count += 1
                    channel_results.append(
                        ChannelStatus(
                            channel=channel,
                            status=NotificationStatusEnum.SENT,
                            sent_at=datetime.now(timezone.utc),
                            provider_reference=result.get("provider_reference"),
                        )
                    )
                    logger.info(
                        f"Successfully sent {channel} notification to {contact_info}: {notification_id}"
                    )
                else:
                    channel_results.append(
                        ChannelStatus(
                            channel=channel,
                            status=NotificationStatusEnum.FAILED,
                            error_code=result.get("error_code", "SEND_ERROR"),
                            error_message=result.get("error_message"),
                        )
                    )
                    logger.warning(
                        f"Failed to send {channel} notification: {result.get('error_message')}"
                    )

            except Exception as e:
                logger.error(f"Error sending {channel} notification: {e}")
                channel_results.append(
                    ChannelStatus(
                        channel=channel,
                        status=NotificationStatusEnum.FAILED,
                        error_code="SEND_ERROR",
                        error_message=str(e),
                    )
                )

        # Update notification with results
        notification.channel_status = channel_results
        notification.completed_at = datetime.now(timezone.utc)

        # Determine overall status
        if success_count == len(channels_requested):
            notification.status = NotificationStatusEnum.SENT
        elif success_count > 0:
            notification.status = NotificationStatusEnum.PARTIAL
        else:
            notification.status = NotificationStatusEnum.FAILED
            # Retry if not max retries yet
            if notification.retry_count < notification.max_retries:
                await queue.enqueue_retry(notification_id)
                return

        logger.info(f"Completed notification {notification_id}: {notification.status}")

    except Exception as e:
        logger.error(f"Error processing notification {notification_id}: {e}")
