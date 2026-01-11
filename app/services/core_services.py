import uuid
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from app.models import (
    Notification,
    NotificationStatusEnum,
    NotificationTypeEnum,
    ChannelEnum,
    Template,
    TemplateStatusEnum,
    UserPreference,
    NotificationFrequencyEnum,
    ChannelsContent,
    ChannelStatus,
    Recipient,
    PriorityEnum,
)
from jinja2 import Template as Jinja2Template

logger = logging.getLogger(__name__)

# In-memory storage (in production, use database)
NOTIFICATIONS_STORE = {}
TEMPLATES_STORE = {}
USER_PREFERENCES_STORE = {}
DELIVERY_LOGS_STORE = {}


class TemplateService:
    """Service for template management"""

    async def create_template(
        self,
        tenant_id: uuid.UUID,
        name: str,
        notification_type: NotificationTypeEnum,
        channels_content: ChannelsContent,
        required_variables: List[str],
        created_by: Optional[uuid.UUID] = None,
    ) -> Template:
        """Create a new template"""
        template_id = uuid.uuid4()
        template = Template(
            id=template_id,
            tenant_id=tenant_id,
            name=name,
            notification_type=notification_type,
            channels_content=channels_content,
            required_variables=required_variables,
            version="1.0.0",
            status=TemplateStatusEnum.DRAFT,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=created_by,
        )
        TEMPLATES_STORE[str(template_id)] = template
        logger.info(f"Created template: {template_id} in tenant {tenant_id}")
        return template

    async def get_template(self, template_id: uuid.UUID) -> Optional[Template]:
        """Get template by ID"""
        return TEMPLATES_STORE.get(str(template_id))

    async def list_templates(self, tenant_id: uuid.UUID) -> List[Template]:
        """List all templates for tenant"""
        return [
            t for t in TEMPLATES_STORE.values()
            if t.tenant_id == tenant_id
        ]

    async def activate_template(self, template_id: uuid.UUID) -> Optional[Template]:
        """Activate a template"""
        template = TEMPLATES_STORE.get(str(template_id))
        if template:
            template.status = TemplateStatusEnum.ACTIVE
            template.updated_at = datetime.now(timezone.utc)
            logger.info(f"Activated template: {template_id}")
        return template

    async def render_template(
        self,
        template: Template,
        channel: ChannelEnum,
        variables: Dict[str, Any],
    ) -> Dict[str, str]:
        """Render template content with variable substitution"""
        channel_content = getattr(template.channels_content, channel.value, None)
        if not channel_content:
            raise ValueError(f"Template has no content for channel: {channel}")

        rendered = {}
        for key, template_str in channel_content.items():
            if template_str:
                try:
                    jinja_template = Jinja2Template(template_str)
                    rendered[key] = jinja_template.render(**variables)
                except Exception as e:
                    logger.error(f"Error rendering template: {e}")
                    raise
        return rendered


class PreferenceService:
    """Service for user preference management"""

    async def get_user_preferences(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UserPreference:
        """Get user notification preferences"""
        key = f"{tenant_id}:{user_id}"
        if key not in USER_PREFERENCES_STORE:
            # Create default preferences if not exists
            preference = UserPreference(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                opted_out_channels=[],
                opted_out_notification_types=[],
                global_opt_out=False,
                notification_frequency=NotificationFrequencyEnum.INSTANT,
                updated_at=datetime.now(timezone.utc),
            )
            USER_PREFERENCES_STORE[key] = preference
        return USER_PREFERENCES_STORE[key]

    async def update_user_preferences(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        opted_out_channels: Optional[List[ChannelEnum]] = None,
        opted_out_notification_types: Optional[List[NotificationTypeEnum]] = None,
        global_opt_out: Optional[bool] = None,
        notification_frequency: Optional[NotificationFrequencyEnum] = None,
    ) -> UserPreference:
        """Update user notification preferences"""
        preferences = await self.get_user_preferences(tenant_id, user_id)

        if opted_out_channels is not None:
            preferences.opted_out_channels = opted_out_channels
        if opted_out_notification_types is not None:
            preferences.opted_out_notification_types = opted_out_notification_types
        if global_opt_out is not None:
            preferences.global_opt_out = global_opt_out
        if notification_frequency is not None:
            preferences.notification_frequency = notification_frequency

        preferences.updated_at = datetime.now(timezone.utc)
        key = f"{tenant_id}:{user_id}"
        USER_PREFERENCES_STORE[key] = preferences

        logger.info(f"Updated preferences for user {user_id} in tenant {tenant_id}")
        return preferences

    async def is_opted_out(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        channel: ChannelEnum,
        notification_type: NotificationTypeEnum,
    ) -> bool:
        """Check if user is opted out from a specific channel/type"""
        preferences = await self.get_user_preferences(tenant_id, user_id)

        # Check global opt-out
        if preferences.global_opt_out:
            return True

        # Check channel opt-out
        if channel in preferences.opted_out_channels:
            return True

        # Check notification type opt-out
        if notification_type in preferences.opted_out_notification_types:
            return True

        return False


class NotificationService:
    """Service for notification creation and status tracking"""

    def __init__(self, template_service: TemplateService, preference_service: PreferenceService):
        self.template_service = template_service
        self.preference_service = preference_service

    async def create_notification(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_type: NotificationTypeEnum,
        recipient: Recipient,
        channels: List[ChannelEnum],
        template_id: uuid.UUID,
        template_variables: Dict[str, Any],
        priority: PriorityEnum = PriorityEnum.NORMAL,
        correlation_id: Optional[uuid.UUID] = None,
        send_at: Optional[datetime] = None,
    ) -> Notification:
        """Create a new notification"""
        if not correlation_id:
            correlation_id = uuid.uuid4()

        notification_id = uuid.uuid4()

        # Get template
        template = await self.template_service.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Create channel statuses
        channel_statuses = [
            ChannelStatus(
                channel=channel,
                status=NotificationStatusEnum.QUEUED,
            )
            for channel in channels
        ]

        notification = Notification(
            id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            recipient=recipient,
            channels_requested=channels,
            template_id=template_id,
            template_version=template.version,
            template_variables=template_variables,
            priority=priority,
            status=NotificationStatusEnum.QUEUED,
            channel_status=channel_statuses,
            scheduled_at=send_at,
            queued_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        NOTIFICATIONS_STORE[str(notification_id)] = notification
        logger.info(f"Created notification: {notification_id} for user {user_id}")
        return notification

    async def get_notification(self, notification_id: uuid.UUID) -> Optional[Notification]:
        """Get notification by ID"""
        return NOTIFICATIONS_STORE.get(str(notification_id))

    async def list_notifications(
        self,
        tenant_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        notification_type: Optional[NotificationTypeEnum] = None,
        status: Optional[NotificationStatusEnum] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Notification], int]:
        """List notifications with filtering"""
        notifications = [
            n for n in NOTIFICATIONS_STORE.values()
            if n.tenant_id == tenant_id
            and (user_id is None or n.user_id == user_id)
            and (notification_type is None or n.notification_type == notification_type)
            and (status is None or n.status == status)
        ]

        total = len(notifications)
        paginated = notifications[offset : offset + limit]
        return paginated, total

    async def update_notification_status(
        self,
        notification_id: uuid.UUID,
        status: NotificationStatusEnum,
        channel_statuses: Optional[List[ChannelStatus]] = None,
    ) -> Optional[Notification]:
        """Update notification status"""
        notification = NOTIFICATIONS_STORE.get(str(notification_id))
        if notification:
            notification.status = status
            if channel_statuses:
                notification.channel_status = channel_statuses
            notification.updated_at = datetime.now(timezone.utc)

            if status == NotificationStatusEnum.SENT:
                notification.sent_at = datetime.now(timezone.utc)

            logger.info(f"Updated notification {notification_id} status to {status}")
        return notification

    async def retry_notification(
        self,
        notification_id: uuid.UUID,
        max_retries: int = 3,
    ) -> Optional[Notification]:
        """Increment retry count and reschedule notification"""
        notification = NOTIFICATIONS_STORE.get(str(notification_id))
        if notification:
            if notification.retry_count < max_retries:
                notification.retry_count += 1
                # Exponential backoff: 1s, 2s, 4s, etc.
                backoff_seconds = min(2 ** notification.retry_count, 300)
                notification.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                notification.updated_at = datetime.now(timezone.utc)
                logger.info(
                    f"Scheduled retry for notification {notification_id}, "
                    f"attempt {notification.retry_count} at {notification.next_retry_at}"
                )
            else:
                logger.warning(f"Max retries reached for notification {notification_id}")
        return notification
