import pytest
import uuid
import os
from unittest.mock import MagicMock, patch

# Note: TESTING environment variable should be managed by individual test fixtures
# Don't set it globally here to allow auth tests to work properly

from app.models import (
    NotificationTypeEnum,
    ChannelEnum,
    TemplateStatusEnum,
    NotificationFrequencyEnum,
    ChannelsContent,
    Recipient,
)
from app.services import TemplateService, PreferenceService, NotificationService


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis connections for testing"""
    with patch("app.queue.redis_queue.redis.Redis"):
        yield


@pytest.fixture
def mock_jwt_token():
    """Generate a valid mock JWT token for testing"""
    import json
    import base64

    header = json.dumps({"alg": "HS256", "typ": "JWT"})
    payload = json.dumps({
        "user_id": "12345678-1234-4567-a8a0-321f97f01f41",
        "tenant_id": "e0ab0899-c00a-4c42-a8a0-321f97f01f41",
        "role": "user",
    })

    header_encoded = base64.urlsafe_b64encode(header.encode()).rstrip(b"=")
    payload_encoded = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=")

    token = f"{header_encoded.decode()}.{payload_encoded.decode()}.signature"
    return token


@pytest.fixture
def tenant_id():
    """Test tenant ID"""
    return uuid.UUID("e0ab0899-c00a-4c42-a8a0-321f97f01f41")


@pytest.fixture
def user_id():
    """Test user ID"""
    return uuid.UUID("12345678-1234-4567-a8a0-321f97f01f41")


@pytest.fixture
def template_service():
    """Template service instance"""
    return TemplateService()


@pytest.fixture
def preference_service():
    """Preference service instance"""
    return PreferenceService()


@pytest.fixture
def notification_service(template_service, preference_service):
    """Notification service instance"""
    return NotificationService(template_service, preference_service)


@pytest.fixture
async def sample_template(template_service, tenant_id, user_id):
    """Create a sample template for testing"""
    template = await template_service.create_template(
        tenant_id=tenant_id,
        name="Test Template",
        notification_type=NotificationTypeEnum.LOAN_APPROVAL,
        channels_content=ChannelsContent(
            email={
                "subject": "Loan Approval",
                "body_html": "<h1>Approved</h1>",
                "body_text": "Approved",
            },
            sms={"content": "Loan approved"},
            push={"title": "Approved", "body": "Loan approved"},
        ),
        required_variables=[],
        created_by=user_id,
    )
    await template_service.activate_template(template.id)
    return template


@pytest.fixture
def sample_recipient():
    """Sample recipient for testing"""
    return Recipient(
        user_id=uuid.uuid4(),
        email="test@example.com",
        phone="+1234567890",
    )
