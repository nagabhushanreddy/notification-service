import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from utils import config, init_utils


# Ensure utils-config reads from the service config directory (respects CONFIG_DIR override)
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "config"))
init_utils(str(CONFIG_DIR))

def _get_bool(key: str, default: bool) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _get_int(key: str, default: int) -> int:
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


class Settings(BaseSettings):
    """Notification service settings loaded via utils.config defaults with env overrides."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Service Configuration
    SERVICE_NAME: str = config.get("service.name", "notification-service")
    SERVICE_VERSION: str = config.get("service.version", "1.0.0")
    ENVIRONMENT: str = config.get("service.environment", "development")
    HOST: str = config.get("server.host", "0.0.0.0")
    PORT: int = _get_int("server.port", 8007)
    WORKERS: int = _get_int("service.workers", 4)
    DEBUG: bool = _get_bool("service.debug", True)

    # Security Configuration
    JWT_SECRET_KEY: str = config.get("jwt.access_secret", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = config.get("jwt.algorithm", "HS256")
    API_KEY_HEADER: str = config.get("api_key.header", "X-API-Key")
    AUTHZ_SERVICE_URL: str = config.get("external_services.authz_service.url", "http://localhost:8001")
    AUTHZ_SERVICE_TIMEOUT: int = _get_int("external_services.authz_service.timeout", 5)
    AUTHZ_SERVICE_RETRY_ATTEMPTS: int = _get_int("external_services.authz_service.retry_attempts", 2)

    # Queue Configuration
    REDIS_HOST: str = config.get("redis.host", "localhost")
    REDIS_PORT: int = _get_int("redis.port", 6379)
    REDIS_DB: int = _get_int("redis.db", 0)
    REDIS_PASSWORD: Optional[str] = config.get("redis.password")
    QUEUE_BATCH_SIZE: int = _get_int("notification.queue_batch_size", 10)
    WORKER_COUNT: int = _get_int("notification.worker_count", 2)

    # Channel Provider Configuration
    EMAIL_PROVIDER: str = config.get("notification_channels.email.provider", "smtp")
    EMAIL_SMTP_HOST: str = config.get("notification_channels.email.smtp_host", "localhost")
    EMAIL_SMTP_PORT: int = _get_int("notification_channels.email.smtp_port", 587)
    EMAIL_FROM_ADDRESS: str = config.get("notification_channels.email.from_address", "noreply@multifinance.com")
    EMAIL_TLS_ENABLED: bool = _get_bool("notification_channels.email.tls_enabled", True)

    SMS_PROVIDER: str = config.get("notification_channels.sms.provider", "twilio")
    SMS_API_KEY: Optional[str] = config.get("notification_channels.sms.api_key")
    SMS_API_SECRET: Optional[str] = config.get("notification_channels.sms.api_secret")
    SMS_FROM_NUMBER: Optional[str] = config.get("notification_channels.sms.from_number")

    WHATSAPP_PROVIDER: str = config.get("notification_channels.whatsapp.provider", "twilio")
    WHATSAPP_API_KEY: Optional[str] = config.get("notification_channels.whatsapp.api_key")
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = config.get("notification_channels.whatsapp.phone_number_id")
    WHATSAPP_BUSINESS_ACCOUNT_ID: Optional[str] = config.get("notification_channels.whatsapp.business_account_id")

    PUSH_PROVIDER: str = config.get("notification_channels.push.provider", "fcm")
    PUSH_API_KEY: Optional[str] = config.get("notification_channels.push.api_key")

    # Business Configuration
    MAX_RETRIES_DEFAULT: int = _get_int("notification.max_retries", 3)
    INITIAL_BACKOFF_SECONDS: float = _get_float("notification.initial_backoff_seconds", 1.0)
    MAX_BACKOFF_SECONDS: float = _get_float("notification.max_backoff_seconds", 300.0)
    RATE_LIMIT_PER_MINUTE: int = _get_int("rate_limiting.max_requests_per_minute", 1000)
    RATE_LIMIT_PER_HOUR: int = _get_int("rate_limiting.max_requests_per_hour", 10000)

    # External Services Configuration
    ENTITY_SERVICE_URL: str = config.get("external_services.entity_service.url", "http://localhost:8002")
    ENTITY_SERVICE_TIMEOUT: int = _get_int("external_services.entity_service.timeout", 10)
    ENTITY_SERVICE_RETRY_ATTEMPTS: int = _get_int("external_services.entity_service.retry_attempts", 3)

    DOCUMENT_SERVICE_URL: str = config.get("external_services.document_service.url", "http://localhost:8003")
    DOCUMENT_SERVICE_TIMEOUT: int = _get_int("external_services.document_service.timeout", 10)
    DOCUMENT_SERVICE_RETRY_ATTEMPTS: int = _get_int("external_services.document_service.retry_attempts", 3)

    # Logging Configuration
    LOG_LEVEL: str = config.get("logging.level", "INFO")
    LOG_FORMAT: str = config.get("logging.format", "json")

    # Database Configuration (optional)
    DATABASE_URL: Optional[str] = config.get("database.url")
    
    # Testing Configuration
    TESTING: bool = _get_bool("TESTING", False)

    # Feature Flags
    ENABLE_EMAIL: bool = _get_bool("notification_channels.email.enabled", True)
    ENABLE_SMS: bool = _get_bool("notification_channels.sms.enabled", True)
    ENABLE_WHATSAPP: bool = _get_bool("notification_channels.whatsapp.enabled", True)
    ENABLE_PUSH: bool = _get_bool("notification_channels.push.enabled", True)


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
