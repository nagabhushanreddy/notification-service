import uuid
import pytest
from datetime import datetime, timedelta, timezone
from app.models import (
    NotificationTypeEnum,
    ChannelEnum,
    NotificationStatusEnum,
    PriorityEnum,
    TemplateStatusEnum,
    NotificationFrequencyEnum,
    ChannelsContent,
    Recipient,
)
from app.services import (
    TemplateService,
    PreferenceService,
    NotificationService,
)


@pytest.fixture
def template_service():
    return TemplateService()


@pytest.fixture
def preference_service():
    return PreferenceService()


@pytest.fixture
def notification_service(template_service, preference_service):
    return NotificationService(template_service, preference_service)


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def user_id():
    return uuid.uuid4()


class TestTemplateService:
    """Tests for TemplateService"""

    @pytest.mark.asyncio
    async def test_create_template(self, template_service, tenant_id, user_id):
        """Test creating a new template"""
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved",
                    "body_html": "<h1>{{ user_name }}, your loan is approved</h1>",
                    "body_text": "{{ user_name }}, your loan is approved",
                }
            ),
            required_variables=["user_name"],
            created_by=user_id,
        )

        assert template.id is not None
        assert template.tenant_id == tenant_id
        assert template.name == "Test Template"
        assert template.status == TemplateStatusEnum.DRAFT
        assert template.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_template(self, template_service, tenant_id, user_id):
        """Test retrieving a template"""
        created_template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={"subject": "Test", "body_html": "Test", "body_text": "Test"}
            ),
            required_variables=[],
            created_by=user_id,
        )

        retrieved_template = await template_service.get_template(created_template.id)

        assert retrieved_template is not None
        assert retrieved_template.id == created_template.id
        assert retrieved_template.name == "Test Template"

    @pytest.mark.asyncio
    async def test_list_templates(self, template_service, tenant_id, user_id):
        """Test listing templates"""
        # Create multiple templates
        await template_service.create_template(
            tenant_id=tenant_id,
            name="Template 1",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={"subject": "Test", "body_html": "Test", "body_text": "Test"}
            ),
            required_variables=[],
            created_by=user_id,
        )

        await template_service.create_template(
            tenant_id=tenant_id,
            name="Template 2",
            notification_type=NotificationTypeEnum.LOAN_REJECTION,
            channels_content=ChannelsContent(
                sms={"content": "Your loan was rejected"}
            ),
            required_variables=[],
            created_by=user_id,
        )

        templates = await template_service.list_templates(tenant_id)

        assert len(templates) >= 2

    @pytest.mark.asyncio
    async def test_activate_template(self, template_service, tenant_id, user_id):
        """Test activating a template"""
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={"subject": "Test", "body_html": "Test", "body_text": "Test"}
            ),
            required_variables=[],
            created_by=user_id,
        )

        assert template.status == TemplateStatusEnum.DRAFT

        activated = await template_service.activate_template(template.id)

        assert activated.status == TemplateStatusEnum.ACTIVE

    @pytest.mark.asyncio
    async def test_render_template(self, template_service, tenant_id, user_id):
        """Test rendering template with variables"""
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved for {{ user_name }}",
                    "body_html": "<h1>Hello {{ user_name }}, Amount: {{ amount }}</h1>",
                    "body_text": "Hello {{ user_name }}, Amount: {{ amount }}",
                }
            ),
            required_variables=["user_name", "amount"],
            created_by=user_id,
        )

        rendered = await template_service.render_template(
            template,
            ChannelEnum.EMAIL,
            {"user_name": "John Doe", "amount": "10000"},
        )

        assert "John Doe" in rendered["body_html"]
        assert "10000" in rendered["body_html"]


class TestPreferenceService:
    """Tests for PreferenceService"""

    @pytest.mark.asyncio
    async def test_get_default_preferences(self, preference_service, tenant_id, user_id):
        """Test getting default preferences for new user"""
        prefs = await preference_service.get_user_preferences(tenant_id, user_id)

        assert prefs.user_id == user_id
        assert prefs.global_opt_out is False
        assert len(prefs.opted_out_channels) == 0
        assert len(prefs.opted_out_notification_types) == 0
        assert prefs.notification_frequency == NotificationFrequencyEnum.INSTANT

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, preference_service, tenant_id, user_id):
        """Test updating user preferences"""
        updated = await preference_service.update_user_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
            opted_out_channels=[ChannelEnum.SMS, ChannelEnum.PUSH],
            global_opt_out=False,
        )

        assert ChannelEnum.SMS in updated.opted_out_channels
        assert ChannelEnum.PUSH in updated.opted_out_channels
        assert ChannelEnum.EMAIL not in updated.opted_out_channels

    @pytest.mark.asyncio
    async def test_is_opted_out_channel(self, preference_service, tenant_id, user_id):
        """Test checking if user opted out from channel"""
        await preference_service.update_user_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
            opted_out_channels=[ChannelEnum.SMS],
        )

        is_opted_out = await preference_service.is_opted_out(
            tenant_id, user_id, ChannelEnum.SMS, NotificationTypeEnum.LOAN_APPROVAL
        )

        assert is_opted_out is True

        is_not_opted_out = await preference_service.is_opted_out(
            tenant_id, user_id, ChannelEnum.EMAIL, NotificationTypeEnum.LOAN_APPROVAL
        )

        assert is_not_opted_out is False

    @pytest.mark.asyncio
    async def test_global_opt_out(self, preference_service, tenant_id, user_id):
        """Test global opt-out"""
        await preference_service.update_user_preferences(
            tenant_id=tenant_id,
            user_id=user_id,
            global_opt_out=True,
        )

        # User should be opted out of all channels and types
        for channel in [ChannelEnum.EMAIL, ChannelEnum.SMS, ChannelEnum.WHATSAPP, ChannelEnum.PUSH]:
            is_opted_out = await preference_service.is_opted_out(
                tenant_id, user_id, channel, NotificationTypeEnum.LOAN_APPROVAL
            )
            assert is_opted_out is True


class TestNotificationService:
    """Tests for NotificationService"""

    @pytest.mark.asyncio
    async def test_create_notification(
        self, notification_service, template_service, tenant_id, user_id
    ):
        """Test creating a notification"""
        # Create template first
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved",
                    "body_html": "<h1>Loan Approved</h1>",
                    "body_text": "Loan Approved",
                }
            ),
            required_variables=[],
            created_by=user_id,
        )
        await template_service.activate_template(template.id)

        recipient = Recipient(user_id=user_id, email="test@example.com")

        notification = await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            recipient=recipient,
            channels=[ChannelEnum.EMAIL],
            template_id=template.id,
            template_variables={},
        )

        assert notification.id is not None
        assert notification.status == NotificationStatusEnum.QUEUED
        assert len(notification.channel_status) == 1
        assert notification.channel_status[0].channel == ChannelEnum.EMAIL

    @pytest.mark.asyncio
    async def test_get_notification(
        self, notification_service, template_service, tenant_id, user_id
    ):
        """Test retrieving a notification"""
        # Create template first
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved",
                    "body_html": "<h1>Loan Approved</h1>",
                    "body_text": "Loan Approved",
                }
            ),
            required_variables=[],
            created_by=user_id,
        )
        await template_service.activate_template(template.id)

        recipient = Recipient(user_id=user_id, email="test@example.com")

        created = await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            recipient=recipient,
            channels=[ChannelEnum.EMAIL],
            template_id=template.id,
            template_variables={},
        )

        retrieved = await notification_service.get_notification(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_update_notification_status(
        self, notification_service, template_service, tenant_id, user_id
    ):
        """Test updating notification status"""
        # Create template first
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved",
                    "body_html": "<h1>Loan Approved</h1>",
                    "body_text": "Loan Approved",
                }
            ),
            required_variables=[],
            created_by=user_id,
        )
        await template_service.activate_template(template.id)

        recipient = Recipient(user_id=user_id, email="test@example.com")

        notification = await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            recipient=recipient,
            channels=[ChannelEnum.EMAIL],
            template_id=template.id,
            template_variables={},
        )

        updated = await notification_service.update_notification_status(
            notification.id,
            NotificationStatusEnum.SENT,
        )

        assert updated.status == NotificationStatusEnum.SENT
        assert updated.sent_at is not None

    @pytest.mark.asyncio
    async def test_retry_notification(
        self, notification_service, template_service, tenant_id, user_id
    ):
        """Test retrying a notification"""
        # Create template first
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved",
                    "body_html": "<h1>Loan Approved</h1>",
                    "body_text": "Loan Approved",
                }
            ),
            required_variables=[],
            created_by=user_id,
        )
        await template_service.activate_template(template.id)

        recipient = Recipient(user_id=user_id, email="test@example.com")

        notification = await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            recipient=recipient,
            channels=[ChannelEnum.EMAIL],
            template_id=template.id,
            template_variables={},
        )

        initial_retry_count = notification.retry_count
        retried = await notification_service.retry_notification(notification.id)

        assert retried.retry_count == initial_retry_count + 1
        assert retried.next_retry_at is not None
        assert retried.next_retry_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_list_notifications(
        self, notification_service, template_service, tenant_id, user_id
    ):
        """Test listing notifications"""
        # Create template first
        template = await template_service.create_template(
            tenant_id=tenant_id,
            name="Test Template",
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            channels_content=ChannelsContent(
                email={
                    "subject": "Loan Approved",
                    "body_html": "<h1>Loan Approved</h1>",
                    "body_text": "Loan Approved",
                }
            ),
            required_variables=[],
            created_by=user_id,
        )
        await template_service.activate_template(template.id)

        recipient = Recipient(user_id=user_id, email="test@example.com")

        created = await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            recipient=recipient,
            channels=[ChannelEnum.EMAIL],
            template_id=template.id,
            template_variables={},
        )

        await notification_service.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=NotificationTypeEnum.LOAN_APPROVAL,
            recipient=recipient,
            channels=[ChannelEnum.SMS],
            template_id=template.id,
            template_variables={},
        )

        notifications, total = await notification_service.list_notifications(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        assert total >= 2
        assert len(notifications) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
