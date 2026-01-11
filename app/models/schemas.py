from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# Enums
class NotificationTypeEnum(str, Enum):
    PROFILE_UPDATE = "profile_update"
    LOAN_APPLICATION = "loan_application"
    LOAN_APPROVAL = "loan_approval"
    LOAN_REJECTION = "loan_rejection"
    LOAN_DISBURSEMENT = "loan_disbursement"
    DOCUMENT_UPLOADED = "document_uploaded"
    PAYMENT_REMINDER = "payment_reminder"
    KYC_STATUS = "kyc_status"
    GENERAL_ALERT = "general_alert"


class ChannelEnum(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"


class NotificationStatusEnum(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    PARTIAL = "partial"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPTED_OUT = "opted_out"


class PriorityEnum(str, Enum):
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TemplateStatusEnum(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class NotificationFrequencyEnum(str, Enum):
    INSTANT = "instant"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"
    OFF = "off"


# Channel Status Models
class ChannelStatus(BaseModel):
    channel: ChannelEnum
    status: NotificationStatusEnum
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    provider_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempt_number: int = 1
    is_final_attempt: bool = False


# Recipient Model
class Recipient(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    user_id: Optional[UUID] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_id: Optional[str] = None


# Template Models
class ChannelsContent(BaseModel):
    email: Optional[Dict[str, str]] = None  # {subject, body_html, body_text}
    sms: Optional[Dict[str, str]] = None  # {content}
    whatsapp: Optional[Dict[str, Any]] = None  # {content, media_urls}
    push: Optional[Dict[str, str]] = None  # {title, body}


class TemplateCreateRequest(BaseModel):
    template_name: str
    notification_type: NotificationTypeEnum
    channels_content: ChannelsContent
    required_variables: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class TemplateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    template_name: str
    notification_type: NotificationTypeEnum
    channels_content: ChannelsContent
    required_variables: List[str]
    version: str
    status: TemplateStatusEnum
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None


class TemplateUpdateRequest(BaseModel):
    status: Optional[TemplateStatusEnum] = None
    version: Optional[str] = None


# Notification Models
class NotificationSendRequest(BaseModel):
    recipient: Recipient
    notification_type: NotificationTypeEnum
    channels: List[ChannelEnum] = Field(min_length=1)
    template_id: Optional[UUID] = None
    template_variables: Dict[str, Any] = Field(default_factory=dict)
    priority: PriorityEnum = PriorityEnum.NORMAL
    send_at: Optional[datetime] = None
    correlation_id: Optional[UUID] = None


class NotificationBatchRequest(BaseModel):
    notifications: List[NotificationSendRequest] = Field(max_length=100)
    common_template_variables: Dict[str, Any] = Field(default_factory=dict)


class DeliveryStatus(BaseModel):
    notification_id: UUID
    status: NotificationStatusEnum
    channel_status: List[ChannelStatus]
    created_at: datetime
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    notification_id: UUID
    status: NotificationStatusEnum
    metadata: Dict[str, Any]


class NotificationBatchResponse(BaseModel):
    batch_id: UUID
    status: NotificationStatusEnum
    summary: Dict[str, Any]
    notification_ids: List[UUID]


class NotificationStatusResponse(BaseModel):
    id: UUID
    notification_type: NotificationTypeEnum
    status: NotificationStatusEnum
    channel_status: List[ChannelStatus]
    recipient: Recipient
    created_at: datetime
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retry_count: int
    next_retry_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    notifications: List[NotificationStatusResponse]
    total: int
    page: int
    page_size: int


# User Preference Models
class UserPreferenceRequest(BaseModel):
    opted_out_channels: Optional[List[ChannelEnum]] = None
    opted_out_notification_types: Optional[List[NotificationTypeEnum]] = None
    global_opt_out: Optional[bool] = None
    notification_frequency: Optional[NotificationFrequencyEnum] = None
    preferred_contact_channel: Optional[ChannelEnum] = None


class UserPreferenceResponse(BaseModel):
    user_id: UUID
    opted_out_channels: List[ChannelEnum]
    opted_out_notification_types: List[NotificationTypeEnum]
    global_opt_out: bool
    notification_frequency: NotificationFrequencyEnum
    preferred_contact_channel: Optional[ChannelEnum] = None
    updated_at: datetime


# Channel Configuration Models
class RetryConfig(BaseModel):
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 300.0


class ChannelConfigRequest(BaseModel):
    channel: ChannelEnum
    enabled: bool
    provider_config: Dict[str, Any]
    rate_limit_per_minute: int = 1000
    retry_config: RetryConfig = Field(default_factory=RetryConfig)


class ChannelConfigResponse(BaseModel):
    id: UUID
    channel: ChannelEnum
    enabled: bool
    rate_limit_per_minute: int
    retry_config: RetryConfig
    last_tested_at: Optional[datetime] = None
    test_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Notification Type Rules
class ChannelRules(BaseModel):
    enabled: bool = True
    rate_limit_per_hour: int = 100
    max_daily_count: int = 1000
    retry_attempts: int = 3


class NotificationTypeRuleRequest(BaseModel):
    notification_type: NotificationTypeEnum
    channel_rules: Dict[ChannelEnum, ChannelRules]
    default_priority: PriorityEnum = PriorityEnum.NORMAL
    batching_allowed: bool = True


class NotificationTypeRuleResponse(BaseModel):
    notification_type: NotificationTypeEnum
    channel_rules: Dict[ChannelEnum, ChannelRules]
    default_priority: PriorityEnum
    batching_allowed: bool
    created_at: datetime
    updated_at: datetime


# Health Check Models
class ProviderHealth(BaseModel):
    provider: str
    status: str
    last_check_at: Optional[datetime] = None


class DetailedHealthResponse(BaseModel):
    status: str
    queue_depth: int
    provider_status: List[ProviderHealth]
    error_rate: float
    response_times: Dict[str, float]


# Report Models
class DeliveryReportResponse(BaseModel):
    summary: Dict[str, Any]
    by_channel: Dict[ChannelEnum, Dict[str, Any]]
    by_notification_type: Dict[NotificationTypeEnum, Dict[str, Any]]
    common_error_codes: Dict[str, int]


# Error Response
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    data: Optional[Any] = None
    metadata: Dict[str, Any]


# Internal Domain Models
class Notification(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    notification_type: NotificationTypeEnum
    recipient: Recipient
    channels_requested: List[ChannelEnum]
    template_id: UUID
    template_version: str
    template_variables: Dict[str, Any]
    priority: PriorityEnum
    status: NotificationStatusEnum
    channel_status: List[ChannelStatus]
    scheduled_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    max_retries: int = 3
    created_by: Optional[UUID] = None
    correlation_id: UUID
    created_at: datetime
    updated_at: datetime


class Template(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    tenant_id: UUID
    name: str
    notification_type: NotificationTypeEnum
    channels_content: ChannelsContent
    required_variables: List[str]
    asset_references: List[str] = Field(default_factory=list)
    version: str
    status: TemplateStatusEnum
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None


class UserPreference(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    opted_out_channels: List[ChannelEnum] = Field(default_factory=list)
    opted_out_notification_types: List[NotificationTypeEnum] = Field(default_factory=list)
    global_opt_out: bool = False
    notification_frequency: NotificationFrequencyEnum = NotificationFrequencyEnum.INSTANT
    preferred_contact_channel: Optional[ChannelEnum] = None
    do_not_call: bool = False
    do_not_email: bool = False
    updated_at: datetime
    updated_by: Optional[UUID] = None


class DeliveryLog(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    notification_id: UUID
    channel: ChannelEnum
    status: NotificationStatusEnum
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    provider_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempt_number: int
    is_final_attempt: bool
    created_at: datetime
