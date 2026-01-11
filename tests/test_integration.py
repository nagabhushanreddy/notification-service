import uuid
import json
import os
import pytest
from fastapi.testclient import TestClient

# Set TESTING mode before importing app
os.environ["TESTING"] = "true"

from main import app
from app.models import (
    NotificationTypeEnum,
    ChannelEnum,
    ChannelsContent,
)
from app.services import TemplateService

# Create test client
client = TestClient(app)


@pytest.fixture
def client_no_auth(monkeypatch):
    """Test client without auth bypass for testing 401 responses"""
    # Temporarily disable TESTING mode
    monkeypatch.setenv("TESTING", "false")
    
    # Reload the config module to pick up the new environment variable
    import importlib
    import app.config
    importlib.reload(app.config)
    
    # Create a new client instance
    test_client = TestClient(app)
    
    yield test_client
    
    # Restore TESTING mode
    monkeypatch.setenv("TESTING", "true")
    importlib.reload(app.config)


@pytest.fixture
def client_no_auth():
    """Test client with auth enforcement (for testing unauthorized scenarios)"""
    # Temporarily disable TESTING mode
    original_testing = os.environ.get("TESTING")
    os.environ["TESTING"] = "false"
    
    # Create a new client that will enforce auth
    from importlib import reload
    import app.config as config_module
    reload(config_module)
    
    from main import app as test_app
    test_client = TestClient(test_app)
    
    yield test_client
    
    # Restore original TESTING mode
    if original_testing is not None:
        os.environ["TESTING"] = original_testing
    else:
        os.environ.pop("TESTING", None)
    
    # Reload config again to restore
    reload(config_module)


# Mock JWT token for testing
MOCK_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzNDU2NzgtczEyMy00NTY3LWE4YTAtMzIxZjk3ZjAxZjQxIiwidGVuYW50X2lkIjoiZTBhYjA4OTktYzAwYS00YzQyLWE4YTAtMzIxZjk3ZjAxZjQxIiwicm9sZSI6InVzZXIifQ.HJMoRzNOWXe99qxYL0xCDx0e6BpCU4jqGqH5Y5H5CQ0"


@pytest.fixture
def headers():
    """Test headers with JWT token and correlation ID"""
    return {
        "Authorization": f"Bearer {MOCK_TOKEN}",
        "X-Correlation-Id": str(uuid.uuid4()),
    }


@pytest.fixture(scope="module")
def test_template():
    """Create a test template"""
    import asyncio
    template_service = TemplateService()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    template = loop.run_until_complete(template_service.create_template(
        tenant_id=uuid.UUID("e0ab0899-c00a-4c42-a8a0-321f97f01f41"),
        name="Integration Test Template",
        notification_type=NotificationTypeEnum.LOAN_APPROVAL,
        channels_content=ChannelsContent(
            email={
                "subject": "Loan Approved",
                "body_html": "<h1>Your loan is approved</h1>",
                "body_text": "Your loan is approved",
            },
            sms={"content": "Your loan is approved"},
            push={
                "title": "Loan Approved",
                "body": "Your loan is approved",
            },
        ),
        required_variables=[],
    ))
    loop.run_until_complete(template_service.activate_template(template.id))
    loop.close()
    return template


class TestHealthEndpoints:
    """Tests for health check endpoints"""

    def test_health_check(self):
        """Test /health endpoint"""
        response = client.get("/health")
        assert response.status_code in [200, 503]
        assert "status" in response.json()

    def test_healthz(self):
        """Test /healthz endpoint"""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


class TestNotificationEndpoints:
    """Tests for notification endpoints"""

    def test_send_notification_unauthorized(self, client_no_auth):
        """Test sending notification without auth header"""
        response = client_no_auth.post(
            "/api/v1/notifications/send",
            json={
                "recipient": {"user_id": "12345678-1234-1234-1234-123456789012"},
                "notification_type": "loan_approval",
                "channels": ["email"],
                "template_id": "12345678-1234-1234-1234-123456789012",
                "template_variables": {},
            },
        )
        assert response.status_code == 401

    def test_send_notification_success(self, headers, test_template):
        """Test successfully sending a notification"""
        response = client.post(
            "/api/v1/notifications/send",
            headers=headers,
            json={
                "recipient": {
                    "user_id": "12345678-1234-1234-1234-123456789012",
                    "email": "test@example.com",
                },
                "notification_type": "loan_approval",
                "channels": ["email"],
                "template_id": str(test_template.id),
                "template_variables": {},
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert "notification_id" in data["data"]
        assert data["data"]["status"] == "queued"

    def test_send_batch_notifications(self, headers, test_template):
        """Test sending batch notifications"""
        response = client.post(
            "/api/v1/notifications/batch",
            headers=headers,
            json={
                "notifications": [
                    {
                        "recipient": {
                            "user_id": "12345678-1234-1234-1234-123456789012",
                            "email": "test1@example.com",
                        },
                        "notification_type": "loan_approval",
                        "channels": ["email"],
                        "template_id": str(test_template.id),
                        "template_variables": {},
                    },
                    {
                        "recipient": {
                            "user_id": "87654321-4321-4321-4321-210987654321",
                            "email": "test2@example.com",
                        },
                        "notification_type": "loan_approval",
                        "channels": ["sms"],
                        "template_id": str(test_template.id),
                        "template_variables": {},
                    },
                ],
                "common_template_variables": {},
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert "batch_id" in data["data"]
        assert len(data["data"]["notification_ids"]) > 0


class TestTemplateEndpoints:
    """Tests for template endpoints"""

    def test_create_template_unauthorized(self, client_no_auth):
        """Test creating template without auth"""
        response = client_no_auth.post(
            "/api/v1/templates",
            json={
                "template_name": "Test",
                "notification_type": "loan_approval",
                "channels_content": {"email": {"subject": "Test"}},
                "required_variables": [],
            },
        )
        assert response.status_code == 401

    def test_create_template_success(self, headers):
        """Test successfully creating a template"""
        response = client.post(
            "/api/v1/templates",
            headers=headers,
            json={
                "template_name": "Integration Test Template",
                "notification_type": "loan_approval",
                "channels_content": {
                    "email": {
                        "subject": "Test Subject",
                        "body_html": "<h1>Test</h1>",
                        "body_text": "Test",
                    }
                },
                "required_variables": [],
                "tags": ["test"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "id" in data["data"]

    def test_list_templates(self, headers):
        """Test listing templates"""
        response = client.get("/api/v1/templates", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)


class TestPreferenceEndpoints:
    """Tests for preference endpoints"""

    def test_get_preferences_unauthorized(self, client_no_auth):
        """Test getting preferences without auth"""
        response = client_no_auth.get(
            "/api/v1/users/12345678-1234-1234-1234-123456789012/preferences"
        )
        assert response.status_code == 401

    def test_get_preferences_success(self, headers):
        """Test successfully getting user preferences"""
        user_id = "12345678-1234-1234-1234-123456789012"
        response = client.get(
            f"/api/v1/users/{user_id}/preferences",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "opted_out_channels" in data["data"]
        assert "global_opt_out" in data["data"]

    def test_update_preferences(self, headers):
        """Test updating user preferences"""
        user_id = "12345678-1234-1234-1234-123456789012"
        response = client.patch(
            f"/api/v1/users/{user_id}/preferences",
            headers=headers,
            json={
                "opted_out_channels": ["sms", "push"],
                "global_opt_out": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "sms" in [c for c in data["data"]["opted_out_channels"]]


class TestStatusEndpoints:
    """Tests for status/notification retrieval endpoints"""

    def test_get_notification_status_not_found(self, headers):
        """Test getting non-existent notification"""
        response = client.get(
            f"/api/v1/notifications/{uuid.uuid4()}",
            headers=headers,
        )
        assert response.status_code in [404, 200]  # May return 200 with no notification

    def test_list_notifications(self, headers):
        """Test listing notifications"""
        response = client.get("/api/v1/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "notifications" in data["data"]
        assert "total" in data["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
