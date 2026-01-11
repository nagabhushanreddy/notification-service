# Multi-Finance User Application
## Notification Service - Requirements Document (OpenAPI-Compliant)

---

## 1. Overview

This document defines the functional and non-functional requirements for the **Notification Service** - a comprehensive, multi-channel notification orchestration system for the Multi-Finance User Web Application built using a **microservices REST architecture**.

The service manages notification delivery across multiple channels (Email, SMS, WhatsApp, Push), supports channel-specific templating, enforces configurable delivery controls at channel and notification-type levels, tracks delivery status, and integrates with document-service for notification assets (images, logos). All APIs must be OpenAPI 3.x compliant.

### Core Responsibility
- **Multi-Channel Delivery**: Send notifications via Email, SMS, WhatsApp, Push notifications
- **Template Management**: Channel-specific templates with variable substitution
- **Delivery Configuration**: Configurable controls per notification-type and channel
- **Status Tracking**: Immutable delivery status and event logging
- **Asset Management**: Integration with document-service for notification assets
- **Retry & Resilience**: Automatic retry with exponential backoff for transient failures
- **Rate Limiting**: Per-user/tenant limits to prevent abuse
- **Opt-Out Management**: Track customer preferences and consent

---

## 2. Architecture Principles

- Microservices with **single responsibility** (notification orchestration only)
- **Asynchronous delivery** (fire-and-forget pattern with status tracking)
- **Queue-based processing** for reliability and scalability (future: event-driven)
- REST APIs with **OpenAPI 3.0+**
- Stateless service nodes
- JWT-based security with authz-service enforcement
- Audit-first: all notification sends logged immutably
- Layered architecture: Routes → Services → Clients → External Systems
- Reuse shared utilities via utils-service
- Pluggable channel providers (extensible architecture)
- Template engine with validation

---

## 3. Features

- **Multi-Channel Support**: Email, SMS, WhatsApp, Push notifications
- **Channel-Specific Templates**: Customize content per channel with dynamic variables
- **Batch Notifications**: Send to multiple recipients in single request
- **Notification Types**: Event-driven (status changes, alerts) and promotional
- **Delivery Configuration**: Enable/disable by channel, notification-type, or user
- **User Preferences**: Track opt-out status per channel
- **Delivery Status Tracking**: Queued, sent, failed, bounced, opted-out
- **Retry Mechanism**: Automatic retry with exponential backoff (configurable)
- **Dead Letter Queue**: Failed notifications after max retries stored for manual review
- **Asset Integration**: Fetch images/logos from document-service for email/WhatsApp
- **Template Management**: Store and manage templates with versioning
- **Personalization**: Variable substitution (user name, loan amount, etc.)
- **Rate Limiting**: Per-user and per-tenant limits
- **Opt-Out Management**: Track user preferences across channels
- **Delivery Reports**: Status summary per notification type
- **Event Webhooks (Future)**: Allow external systems to subscribe to delivery events
- **A/B Testing (Future)**: Test template variations
- **Analytics (Future)**: Delivery metrics and engagement tracking
- **Immutable Audit Trail**: All notification sends logged with timestamps and status
- **Multi-Tenant Isolation**: Strong tenant isolation
- **Utils Integration**: Shared logging, configuration
- **Type Safety**: Full Pydantic schema validation
- **OpenAPI Documentation**: Auto-generated interactive documentation

---

## 4. Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastAPI (async, OpenAPI-native)
- **Data Validation**: Pydantic
- **Message Queue**: Redis (simple pub/sub) or RabbitMQ (if complex workflows needed)
- **Database**: Postgres for notification logs, templates, user preferences; can use entity-service for shared metadata
- **Template Engine**: Jinja2 or similar for variable substitution
- **Email Provider**: SMTP (on-premise) or SaaS (SendGrid, AWS SES)
- **SMS Provider**: Twilio, AWS SNS, or local telecom API
- **WhatsApp Provider**: Twilio, Meta WhatsApp Business API
- **Push Provider**: Firebase Cloud Messaging (FCM), Apple Push Notification (APN)
- **HTTP Client**: httpx for async calls to external providers
- **Logging**: Structured JSON logs via utils-service
- **Testing**: pytest with coverage reporting
- **Server**: Uvicorn ASGI

---

## 5. Core APIs / Endpoints

### 5.1 Health Check
- `GET /health` - Service health and readiness
- `GET /healthz` - Kubernetes liveness probe

### 5.2 Send Notification Endpoints

#### Send Single Notification
**Endpoint**: `POST /api/v1/notifications/send`

**Request Requirements:**
- Must include JWT token in Authorization header
- Must accept recipient information: user_id (UUID) or email/phone/whatsapp_id
- Must accept notification_type (enum: profile_update, loan_application, loan_approval, loan_rejection, loan_disbursement, document_uploaded, payment_reminder, kyc_status, general_alert)
- Must accept channels (array: email, sms, whatsapp, push) - at least one required
- Must accept template_id (string) or inline template content
- Must accept template_variables (object with key-value pairs for substitution)
- Must accept priority (enum: normal, high, urgent - default: normal)
- Must accept send_at (optional ISO 8601 timestamp for scheduled send)
- Must accept correlation_id (optional, default: generated UUID)

**Response Requirements:**
- Success Status: 202 Accepted (async processing)
- Must return notification_id (UUID)
- Must return status (enum: queued, processing, sent, failed)
- Must return metadata: timestamp, correlation_id, channels attempted
- Must return delivery_status per channel if available

**Business Logic:**
- Validate recipient exists and is active
- Check user opt-out preferences per channel
- Skip delivery for opted-out channels (but log attempt)
- Validate template exists and contains all required variables
- Queue notification for async delivery
- Fetch assets from document-service if template references asset URLs
- Check delivery configuration (channel/type level)
- Return immediately (fire-and-forget); delivery happens asynchronously
- Enforce rate limits per user/tenant

**Security:**
- JWT token required; fail closed if missing/invalid
- Verify caller has permission to send to specified recipient (authz-service if needed)
- Sanitize template variables to prevent injection
- Log notification send with caller details

**Error Responses:**
- 400 Bad Request: Invalid recipient, missing template, invalid channels
- 401 Unauthorized: Missing/invalid token
- 403 Forbidden: Insufficient permissions
- 404 Not Found: Template not found
- 422 Unprocessable Entity: Validation errors (template variables)
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Queue/processing failure

---

#### Send Batch Notifications
**Endpoint**: `POST /api/v1/notifications/batch`

**Request Requirements:**
- Must accept array of notification objects (same schema as single send)
- Must accept up to 100 recipients per batch
- Must accept common_template_variables (optional, applied to all notifications)

**Response Requirements:**
- Success Status: 202 Accepted
- Must return batch_id (UUID)
- Must return status: queued, processing, partial, completed
- Must return summary: total, queued, failed, reason for failures
- Must return notification_ids array

**Business Logic:**
- Process notifications in parallel where possible
- Return partial success on some failures
- Log batch operation with batch_id
- Track overall batch completion status

---

#### Resend Notification
**Endpoint**: `POST /api/v1/notifications/{notification_id}/resend`

**Request Requirements:**
- Must include JWT token
- Must accept optional channels (default: retry all channels that failed)
- Must accept optional resend_reason (string)

**Response Requirements:**
- Success Status: 202 Accepted
- Must return notification_id and new delivery attempt ID

**Business Logic:**
- Fetch original notification
- Allow resend only if in failed/partial state
- Check rate limits for resend
- Queue for delivery
- Log resend event with reason

---

### 5.3 Notification Status & Tracking

#### Get Notification Status
**Endpoint**: `GET /api/v1/notifications/{notification_id}`

**Response Requirements:**
- Success Status: 200 OK
- Must return notification object with:
  - id, notification_type, status (overall)
  - channel_status array: channel, status, sent_at, error_code, error_message, provider_reference
  - recipient (user_id or contact info, partially masked)
  - created_at, queued_at, sent_at, delivered_at (if applicable)
  - retry_count, next_retry_at

**Business Logic:**
- Return current status across all channels
- Include delivery timestamps per channel
- Include error details for failed channels
- Mask sensitive recipient data (partial phone/email)

---

#### List Notifications
**Endpoint**: `GET /api/v1/notifications`

**Query Parameters:**
- user_id (optional, filter by recipient)
- notification_type (optional, filter by type)
- status (optional, filter by status: queued, sent, failed, bounced, opted_out)
- channel (optional, filter by channel)
- from_date, to_date (optional, date range filter)
- limit, offset (pagination, default: 50, max: 100)

**Response Requirements:**
- Success Status: 200 OK
- Must return array of notification summaries
- Must include pagination metadata (total, page, page_size)

---

#### Get Delivery Report
**Endpoint**: `GET /api/v1/notifications/reports/delivery`

**Query Parameters:**
- notification_type (optional filter)
- channel (optional filter)
- from_date, to_date (required, date range)

**Response Requirements:**
- Success Status: 200 OK
- Must return summary: total_sent, total_failed, total_bounced, total_opted_out, success_rate
- Must return breakdown per channel: channel, count, success_rate
- Must return breakdown per notification_type: type, count, success_rate
- Must return common error codes: count per error

**Business Logic:**
- Aggregate statistics from notification logs
- Calculate success rate (sent / total)
- Group by channel and type
- Support date range queries

---

### 5.4 Template Management

#### Create/List Templates
**Endpoint**: `POST /api/v1/templates` (create)
**Endpoint**: `GET /api/v1/templates` (list)

**Request Requirements (Create):**
- Must accept template_name (string, unique per tenant)
- Must accept notification_type (enum)
- Must accept channels_content (object) with per-channel content:
  - email: subject, body_html, body_text (plain text fallback)
  - sms: content (max 160 or 320 chars depending on country)
  - whatsapp: content, media_url (optional)
  - push: title, body
- Must accept required_variables (array of variable names used in content)
- Must accept version (optional, default: 1.0.0)
- Must accept tags (optional, array for categorization)

**Response Requirements:**
- Success Status: 201 Created (or 200 OK for list)
- Must return template_id, name, notification_type, channels_content, version, created_at

**Business Logic:**
- Validate template variables are consistent across channels
- Support template versioning (new content = new version)
- Mark as draft until activated
- Validate content length per channel (SMS max chars)
- Check for asset references; validate against document-service

---

#### Activate/Deactivate Template
**Endpoint**: `PATCH /api/v1/templates/{template_id}`

**Request Requirements:**
- Must accept status (enum: draft, active, archived)
- Must accept version (if activating specific version)

**Response Requirements:**
- Success Status: 200 OK
- Must return template with updated status

**Business Logic:**
- Only allow activation of fully configured templates
- Deactivation prevents new sends but doesn't affect queued messages
- Support reverting to previous template versions

---

### 5.5 User Preferences

#### Get User Preferences
**Endpoint**: `GET /api/v1/users/{user_id}/preferences`

**Response Requirements:**
- Success Status: 200 OK
- Must return opted_out_channels (array), opted_out_notification_types (array)
- Must return global_opt_out (boolean)
- Must return notification_frequency (enum: instant, daily_digest, weekly_digest, off)
- Must return preferred_contact_channel (enum)
- Must return updated_at

**Business Logic:**
- Return user-specific delivery preferences
- If global_opt_out=true, skip all notifications for user
- If daily_digest enabled, batch notifications for that user

---

#### Update User Preferences
**Endpoint**: `PATCH /api/v1/users/{user_id}/preferences`

**Request Requirements:**
- Must accept opted_out_channels (optional array to toggle)
- Must accept opted_out_notification_types (optional array)
- Must accept global_opt_out (optional boolean)
- Must accept notification_frequency (optional)
- Must accept preferred_contact_channel (optional)

**Response Requirements:**
- Success Status: 200 OK
- Must return updated preferences
- Must include timestamp

**Business Logic:**
- Only allow user to update own preferences (or admin)
- Log preference changes for audit
- Effective immediately for subsequent sends

---

### 5.6 Channel Configuration (Admin)

#### Configure Channel Settings
**Endpoint**: `POST /api/v1/admin/channels/{channel}/config`

**Request Requirements:**
- Must include JWT token with admin role
- Must accept channel (enum: email, sms, whatsapp, push)
- Must accept enabled (boolean)
- Must accept provider_config (provider-specific settings):
  - email: smtp_host, smtp_port, from_address, tls_enabled
  - sms: provider (twilio/aws_sns), api_key, api_secret, from_number
  - whatsapp: provider, api_key, phone_number_id, business_account_id
  - push: provider (fcm/apn), api_key, certificate (for APN)
- Must accept rate_limit_per_minute (integer)
- Must accept retry_config: max_retries, initial_backoff_seconds, max_backoff_seconds

**Response Requirements:**
- Success Status: 200 OK (if exists) or 201 Created
- Must return channel, enabled, rate_limit, retry_config, last_updated

**Business Logic:**
- Validate provider credentials (test connection if possible)
- Encrypt sensitive config (api keys, certificates)
- Enable/disable channel for all tenants or specific tenant
- Support multiple providers per channel for failover

---

#### Configure Notification Type Rules
**Endpoint**: `POST /api/v1/admin/notification-types/{type}/rules`

**Request Requirements:**
- Must include JWT token with admin role
- Must accept notification_type (enum)
- Must accept channel_rules (object) with per-channel settings:
  - enabled (boolean)
  - rate_limit_per_hour (integer)
  - max_daily_count (integer)
  - retry_attempts (integer)
- Must accept default_priority (enum)
- Must accept batching_allowed (boolean)

**Response Requirements:**
- Success Status: 200 OK
- Must return notification_type and configured rules

**Business Logic:**
- Allow fine-grained control over notification delivery
- Enable/disable entire notification type if needed
- Override channel-level settings per type
- Log configuration changes

---

### 5.7 Admin Management

#### List Dead Letter Queue
**Endpoint**: `GET /api/v1/admin/dead-letter-queue`

**Query Parameters:**
- notification_type (optional filter)
- reason (optional filter)
- from_date, to_date (optional date range)

**Response Requirements:**
- Success Status: 200 OK
- Must return array of failed notifications (exceeding max retries)
- Must include failure reason, last_error, all_attempts summary

---

#### Retry Dead Letter Notification
**Endpoint**: `POST /api/v1/admin/dead-letter-queue/{notification_id}/retry`

**Request Requirements:**
- Must include JWT token with admin role
- Must accept optional retry_reason (string)

**Response Requirements:**
- Success Status: 202 Accepted
- Moves notification back to queue for reprocessing

---

### 5.8 Health & Monitoring

#### Get Notification Service Health
**Endpoint**: `GET /api/v1/admin/health/detailed`

**Response Requirements:**
- Success Status: 200 OK
- Must return service status: healthy, degraded, unhealthy
- Must return queue depth (pending notifications)
- Must return provider status per channel: provider, status, last_check_at
- Must return error rate (last hour)
- Must return response times (P50, P95, P99)

---

## 6. Data Model Requirements (Descriptive)

**Notification Schema:**
- id (UUID), tenant_id (UUID), user_id (UUID)
- notification_type (enum)
- recipient: user_id or email/phone (direct recipient)
- channels_requested (array: email, sms, whatsapp, push)
- template_id (ref), template_version
- template_variables (object, stored for audit)
- priority (enum)
- status (enum: queued, processing, sent, partial, failed, bounced, opted_out)
- channel_status array: channel, status, sent_at, provider_reference, error_code, error_message
- scheduled_at (optional), queued_at, processing_started_at, completed_at
- retry_count, next_retry_at, max_retries
- created_by (user_id, optional - for audit)
- correlation_id (for tracing)
- created_at, updated_at

**Template Schema:**
- id (UUID), tenant_id (UUID)
- name (string, unique per tenant)
- notification_type (enum)
- channels_content (object per channel):
  - email: subject_template, body_html_template, body_text_template
  - sms: content_template (max length per country)
  - whatsapp: content_template, media_urls (array, optional)
  - push: title_template, body_template
- required_variables (array)
- asset_references (array of document_service URLs)
- version (semantic)
- status (enum: draft, active, archived)
- created_at, updated_at, created_by

**User Preference Schema:**
- id (UUID), tenant_id (UUID), user_id (UUID)
- opted_out_channels (array)
- opted_out_notification_types (array)
- global_opt_out (boolean)
- notification_frequency (enum)
- preferred_contact_channel (enum)
- do_not_call (boolean, for SMS)
- do_not_email (boolean)
- updated_at, updated_by (user_id)

**Channel Config Schema:**
- id (UUID), channel (enum)
- enabled (boolean)
- provider (string: smtp, twilio, aws_sns, etc.)
- rate_limit_per_minute (integer)
- retry_config: max_retries, initial_backoff, max_backoff
- provider_config (encrypted): api keys, credentials
- last_tested_at, test_status
- created_at, updated_at

**Notification Type Rule Schema:**
- notification_type (enum)
- channel_rules object:
  - email: enabled, rate_limit_per_hour, max_daily_count, retry_attempts
  - sms: enabled, rate_limit_per_hour, max_daily_count, retry_attempts
  - whatsapp: enabled, rate_limit_per_hour, max_daily_count, retry_attempts
  - push: enabled, rate_limit_per_hour, max_daily_count, retry_attempts
- default_priority (enum)
- batching_allowed (boolean)
- created_at, updated_at

**Delivery Log Schema:**
- id (UUID), notification_id (ref)
- channel (enum)
- status (enum)
- sent_at, delivered_at
- provider_reference (string, from provider)
- error_code, error_message
- attempt_number, is_final_attempt
- created_at

---

## 7. Business Logic & Rules

### 7.1 Notification Send Flow
1. Receive send request with recipient, type, channels, template
2. Validate recipient exists and is active
3. Check global opt-out; skip if opted-out globally
4. Check user preferences per channel; skip opted-out channels
5. Validate template exists with required version
6. Substitute template variables
7. Fetch assets from document-service if referenced
8. Validate content per channel (SMS length, email headers)
9. Check rate limits (per-user, per-tenant, per-type)
10. Check channel-level delivery rules (enabled/disabled)
11. Queue notification for async delivery
12. Return notification_id and queued status
13. Async worker processes: connect to provider, send, track status
14. Log delivery result with timestamp and provider reference

### 7.2 Retry Mechanism
- Initial send fails → queue for retry
- Retry with exponential backoff (e.g., 1s, 2s, 4s, 8s, 16s)
- Configurable max retries per channel (default: 3)
- After max retries → move to dead letter queue
- Admin can manually retry from dead letter queue
- Log all retry attempts

### 7.3 Opt-Out Management
- Customer can opt-out per channel (email, sms, whatsapp, push)
- Customer can opt-out per notification type
- Global opt-out disables all notifications
- Opt-out is immediate and effective
- Opt-in requires explicit re-engagement (confirmation email/SMS)

### 7.4 Rate Limiting
- Per-user limits: max notifications per day per channel
- Per-tenant limits: max notifications per minute per channel
- Per-type limits: e.g., marketing emails max 2 per week
- Breached limits: queue with delay or reject with 429
- Configurable per channel and type

### 7.5 Template Versioning
- New template content = new version
- Active version used for new sends unless version specified
- Previous versions remain queryable for sent notifications
- Support A/B testing via version selection (future)

### 7.6 Asset Management
- Template references document-service URLs for images/logos
- Fetch asset on send (with caching for performance)
- If asset unavailable, proceed without asset (graceful degradation)
- Email: embed images or use URLs
- WhatsApp: attach media as specified by template

### 7.7 Delivery Configuration Hierarchy
- Global channel config (enable/disable channel)
- Per-type channel rules (override global)
- Per-user preferences (opt-out overrides all)
- Result: user opt-out > type rules > channel global setting

### 7.8 Audit & Compliance
- Every send logged with all details
- Opt-out/opt-in changes logged
- Template changes logged
- Configuration changes logged by admin
- Immutable audit trail for compliance

### 7.9 Batching
- Support batch send for bulk notifications (e.g., daily digest)
- Batch notifications processed in parallel
- Partial success allowed; return summary
- Retry failed items individually

### 7.10 Scheduled Sends
- Support send_at parameter for future sends
- Queue scheduled notification
- Process at scheduled time
- Display in queued notifications list

---

## 8. Security Requirements

### 8.1 Authentication
- JWT validation from auth-service
- Token claims include user_id, tenant_id, role
- API key support for service-to-service

### 8.2 Authorization
- End-user can only send to own user_id (or authorized recipients)
- Admin endpoints require admin role (verified via authz-service)
- Channel config and rules require admin role

### 8.3 Data Protection
- Mask recipient contact info in API responses (partial phone/email)
- Encrypt provider credentials in configuration storage
- No sensitive data in logs (api keys, tokens, credentials)
- PII in template variables not logged in full

### 8.4 Validation & Input Hardening
- Validate all input fields (recipient format, template variables)
- Sanitize template variables to prevent injection in content
- Validate URLs for document-service asset references
- Enforce maximum message length per channel
- Prevent directory traversal or similar attacks

### 8.5 Rate Limiting
- Enforce per-user rate limits to prevent abuse
- Enforce per-tenant limits to prevent resource exhaustion
- Return 429 Too Many Requests when exceeded
- Track rate limit violations for monitoring

### 8.6 Audit & Tracing
- Log all notification sends with correlation ID
- Log all preference changes (who changed what, when)
- Log all administrative configuration changes
- Immutable audit trail
- Propagate correlation IDs to downstream services

### 8.7 Provider Security
- Test provider credentials before storing
- Encrypt credentials at rest
- Use secure connections (TLS) to providers
- Rotate credentials periodically (manual process)
- Log failed provider connections for monitoring

---

## 9. Performance Requirements

### 9.1 Latency
- P95 send request acceptance: <100ms (queue only)
- P95 template fetch: <50ms
- P95 user preference check: <30ms
- P95 delivery report query: <200ms (with date range filtering)

### 9.2 Throughput
- Support 10,000 notifications per minute ingestion
- Support 1000 concurrent send requests
- Queue processing: deliver 50,000+ notifications per minute (depends on provider limits)
- Batch operations: 100 recipients per batch

### 9.3 Scalability
- Horizontal scaling via multiple worker nodes (shared queue)
- Queue-based design allows decoupling of send and delivery
- Caching for templates and user preferences
- Pagination for list/report queries

### 9.4 Reliability
- At-least-once delivery semantics (retry until max attempts)
- Queue persistence (not in-memory)
- Health checks for provider connectivity
- Graceful degradation if provider unavailable

---

## 10. Error Handling

### 10.1 Standard Error Response
- success: false (boolean)
- error object: code (ERROR_CODE), message (human-readable), details (optional)
- data: null
- metadata: timestamp (ISO 8601), correlation_id (UUID)

### 10.2 Error Codes
- INVALID_REQUEST: Malformed request, missing required fields
- UNAUTHORIZED: Missing/invalid JWT
- FORBIDDEN: Insufficient permissions
- NOT_FOUND: Recipient, template, or notification not found
- CONFLICT: Template already exists with same name
- UNPROCESSABLE_ENTITY: Validation errors (template variables, content length)
- RATE_LIMITED: Rate limit exceeded
- RECIPIENT_OPTED_OUT: User opted-out of channel/type
- TEMPLATE_NOT_FOUND: Referenced template doesn't exist
- INVALID_TEMPLATE_VARIABLES: Missing or invalid variables
- CHANNEL_DISABLED: Channel not configured or disabled
- DOCUMENT_SERVICE_ERROR: Asset fetch failure
- PROVIDER_ERROR: External provider error (SMTP, Twilio, etc.)
- QUEUE_ERROR: Queue processing failure
- AUTHZ_SERVICE_ERROR: Authorization check failed

---

## 11. External Service Integration

### 11.1 Entity Service
**Purpose**: Optional; store user notification preferences and delivery statistics

**Operations:**
- Query user entity for contact info (email, phone)
- Store notification preferences metadata
- Store delivery statistics per user

**Error Handling:**
- Fail open (proceed without entity-service if available in cache)
- Retry transient failures
- Log integration errors with correlation ID

### 11.2 Document Service
**Purpose**: Fetch notification assets (images, logos) for email/WhatsApp

**Operations:**
- Fetch asset metadata and pre-signed URL
- Download asset for embedding or reference

**Error Handling:**
- Graceful degradation if asset unavailable (send without asset)
- Retry transient failures
- Log asset fetch failures; continue processing

### 11.3 Utils Service
**Purpose**: Shared logging and configuration

**Operations:**
- Initialize structured logging
- Use pre-configured logger instance
- Get configuration from environment/YAML

---

## 12. Testing Requirements

### 12.1 Unit Tests
- Template variable substitution
- Opt-out logic and preference enforcement
- Rate limit calculations
- Content validation per channel (SMS length, email format)
- Retry backoff calculations
- Error code mapping
- Minimum 80% code coverage

### 12.2 Integration Tests
- Send single notification flow (end-to-end)
- Batch send with partial failures
- Retry and dead letter queue
- Template rendering with assets from document-service
- User preference enforcement
- Channel configuration (enable/disable)
- Notification type rules
- Provider integration (mock providers)
- Entity-service integration for preferences

### 12.3 Performance Tests
- Load test: 1000 concurrent send requests
- Queue processing speed: 50k notifications per minute
- Template rendering performance
- Provider connection pooling

### 12.4 Security Tests
- JWT validation and token expiry
- Authorization checks (admin vs. end-user)
- Rate limit enforcement
- Input sanitization (template variable injection)
- Sensitive data masking in responses/logs
- Credential encryption

---

## 13. Configuration Requirements

### 13.1 Application Settings
- Service name: notification-service
- Version and environment tracking
- Server host, port (default: 8007), workers

### 13.2 Security Configuration
- JWT settings: secret key, algorithm (HS256)
- AuthZ-service endpoint, timeout (5s), retry attempts (2)
- API key header name (X-API-Key)

### 13.3 Queue Configuration
- Queue type: Redis (simple) or RabbitMQ (advanced)
- Queue host, port, credentials
- Worker count for async processing
- Batch processing size (default: 10 notifications)

### 13.4 Channel Provider Configuration
- Email: SMTP host, port, from_address, TLS settings
- SMS: Provider (Twilio/AWS SNS), API key, credentials
- WhatsApp: Provider API key, phone_number_id
- Push: FCM/APN credentials

### 13.5 Business Configuration
- Rate limits: per-user, per-tenant, per-type
- Retry settings: max_retries, backoff strategy, max_backoff_seconds
- Max message lengths per channel (SMS 160/320)
- Template asset cache TTL
- User preference cache TTL

### 13.6 External Services Configuration
- Entity-service: base URL, timeout (10s), retry attempts (3)
- Document-service: base URL, timeout (10s), retry attempts (3)
- AuthZ-service: base URL, timeout (5s), retry attempts (2)

### 13.7 Logging Configuration
- Log level (INFO default), JSON format, stdout output
- Mask sensitive data: API keys, credentials, PII
- Enable debug logging for queue operations

---

## 14. Deployment

### 14.1 Container
- Docker image with Python 3.10+ and all dependencies
- Health check endpoint: `/healthz`
- Readiness probe: `/health`
- Liveness probe: `/healthz`
- Background worker process for async delivery

### 14.2 Kubernetes
- API service: minimum 2 replicas for HA
- Worker deployment: configurable replicas (min 2, scale up with queue depth)
- Resource limits (API): CPU 1 core, Memory 1GB
- Resource requests (API): CPU 500m, Memory 512MB
- Resource limits (Worker): CPU 2 cores, Memory 2GB (provider calls)
- Resource requests (Worker): CPU 1 core, Memory 1GB
- HPA for workers based on queue depth
- Persistent storage for queue (Redis or RabbitMQ StatefulSet)

### 14.3 Service Discovery
- API service name: `notification-service`
- Port: 8007
- Protocol: HTTP

### 14.4 Database
- Postgres for notification logs and templates
- Schema migrations with rollback capability
- Indexes on: notification_id, user_id, tenant_id, status, created_at

---

## 15. OpenAPI Requirements

### 15.1 OpenAPI Specification
- Version: OpenAPI 3.0.3
- Title: Notification Service API
- Version: 1.0.0
- Base Path: `/api/v1`

### 15.2 Security Schemes
- **BearerAuth**: HTTP bearer token authentication with JWT format
- **ApiKeyAuth**: API key passed in X-API-Key header for service-to-service

### 15.3 Request/Response Headers
- X-Correlation-Id: Request correlation ID for tracing
- X-Rate-Limit-Remaining: Remaining requests in rate limit window
- X-Rate-Limit-Reset: Timestamp when rate limit resets

### 15.4 Documentation
- Interactive Swagger UI at `/docs`
- ReDoc documentation at `/redoc`
- OpenAPI JSON at `/openapi.json`

---

## 16. Monitoring & Observability

### 16.1 Metrics
- Notification throughput (per minute, per channel)
- Delivery success rate (per channel, per type)
- Provider latency (P50, P95, P99 per provider)
- Queue depth (pending notifications)
- Error rate (per channel, per error code)
- Retry rate and dead letter queue size
- Template rendering time
- Asset fetch latency
- Rate limit violations
- Provider connection failures

### 16.2 Logs
- Structured JSON logs with correlation_id, notification_id, user_id, tenant_id
- Log all notification sends with: recipient, type, channels, status
- Log retry attempts with attempt number and backoff
- Log provider errors with error code and message
- Log configuration changes (template, rules, channel settings)
- Log opt-in/opt-out changes
- Mask sensitive data: API keys, credentials, full PII

### 16.3 Tracing
- Propagate correlation IDs through send, queue, delivery workflow
- Trace document-service asset fetches
- Trace entity-service preference checks
- Trace provider calls with request/response timing

### 16.4 Alerts
- Provider connectivity issues (all retries failed)
- Queue depth exceeding threshold
- High error rate (> 10% of notifications)
- Rate limit violations (possible attack)
- Dead letter queue accumulation
- Entity-service or document-service integration failures
- Template rendering failures

---

## 17. Project Structure (Logical, No Code)

Root entrypoint main.py with FastAPI app initialization, lifespan events (background worker startup), middleware setup.

app/ package containing:
- config.py: Configuration loading from environment and YAML
- middleware.py: Request context, JWT extraction, correlation ID management
- cache.py: Template, user preference, asset caching with TTL
- models/: Pydantic schemas for requests, responses, and domain entities (Notification, Template, UserPreference, ChannelConfig, NotificationTypeRule)
- routes/: API endpoint handlers organized by feature (health, send, status, templates, preferences, admin)
- services/: Business logic layer
  - notification_service: Send, retry, status tracking
  - template_service: Template management and rendering
  - preference_service: User opt-out and preference enforcement
  - channel_service: Per-channel delivery logic
  - retry_service: Backoff calculation, dead letter queue management
  - delivery_service: Provider abstraction and status updates
  - audit_service: Immutable audit trail
- clients/: External service HTTP clients
  - entity_service: User entity and preference metadata
  - document_service: Asset fetch for templates
  - authz_service: Authorization checks (for admin endpoints)
- providers/: Channel provider implementations (pluggable)
  - email_provider: SMTP or SaaS (SendGrid, AWS SES) adapter
  - sms_provider: Twilio, AWS SNS adapter
  - whatsapp_provider: Twilio, Meta WhatsApp Business API adapter
  - push_provider: FCM, APN adapter
  - base_provider: Abstract interface
- queue/: Message queue abstraction (pluggable)
  - redis_queue: Redis pub/sub or list implementation
  - rabbitmq_queue: RabbitMQ implementation (future)
  - base_queue: Abstract queue interface
- workers/: Background worker processes
  - notification_worker: Dequeue and deliver notifications
  - retry_worker: Process retry queue

tests/: Unit and integration tests with conftest.py, mocked providers, reports directory

config/: YAML files for app and logging configuration

requirements.txt and requirements-dev.txt: Dependencies

Standards:
- Each directory with Python code MUST have __init__.py
- Use absolute imports: from app.services import NotificationService
- Export commonly used classes in __init__.py files
- Pluggable architecture: providers and queue backends are swappable
- Keep routes thin (validation + delegation only)
- Business logic in services layer
- External integrations in clients layer
- Use from utils import logger for logging
- Use from utils import init_app_logging for initialization

---

## 18. Future Enhancements

### 18.1 Advanced Features (Phase 2)
- Webhook delivery for external subscribers to delivery events
- A/B testing: test template variations and track performance
- Rich notification formatting (AMP for email, interactive push)
- SMS fallback: if email fails, send SMS instead
- Digest notifications: batch multiple notifications per user
- Multi-language support with language-specific templates
- Customer engagement tracking: open rates, click-through rates
- Complaint handling: bounce management, spam reports

### 18.2 Integration Enhancements (Phase 2)
- Slack notifications for internal alerts
- Telegram bot integration
- In-app notification center (messages stored in user entity)
- Webhook delivery and retry for external systems
- CRM integration: sync preferences with CRM system
- Advanced analytics dashboard with BI tool integration

### 18.3 Personalization (Phase 2)
- Dynamic recipient segmentation (send to customers with specific loan status)
- Predictive send time optimization (when to send for max engagement)
- Personalized content based on user behavior/preferences
- Machine learning for template performance prediction

### 18.4 Compliance & Governance (Phase 2)
- GDPR consent management
- TCPA compliance for SMS (national do-not-call registry)
- Email compliance (CAN-SPAM, CASL)
- WhatsApp business messaging compliance
- Audit log retention policies

---

## 18. Non-Functional Requirements

### 18.1 Testing & Quality Assurance
- **Test Reports Location**: All test reports must be generated in `reports/` folder
  - Coverage reports in `reports/coverage/`
  - Test execution reports in `reports/tests/`
  - Performance test results in `reports/performance/`
  - Security test results in `reports/security/`
- **Code Coverage**: Minimum 80% coverage required for merged code
- **Test Artifacts**: HTML coverage reports, JUnit XML reports for CI/CD integration
- **Continuous Integration**: All tests must pass before deployment
- **Test Isolation**: Each test must be independent and repeatable

### 18.2 Dependency Management
- **Production Dependencies**: `requirements.txt` with pinned versions for reproducible builds
  - Core: fastapi, pydantic, uvicorn
  - Async: httpx, aioredis
  - Templates: jinja2
  - Data Validation: pydantic
  - Logging: python-json-logger (or standard logging)
  - Environment: python-dotenv
  - All dependency versions must be tested and verified
- **Development Dependencies**: `requirements-dev.txt` with all dev tools
  - Testing: pytest, pytest-asyncio, pytest-cov, pytest-mock
  - Code Quality: black, flake8, mypy, pylint
  - Security: bandit
  - Documentation: sphinx (if needed)
  - Utilities: ipython, jupyter
  - Only development dependencies, NOT in production image
- **Dependency Security**: Regular scanning for vulnerable dependencies
- **Lock Files**: Consider using pip-compile or poetry for transitive dependency locking

### 18.3 Version Control
- **Git Ignore**: Comprehensive `.gitignore` file with:
  - Python artifacts: `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.eggs/`, `dist/`, `build/`
  - Virtual environments: `.venv/`, `venv/`, `env/`, `.env*` (except `.env.example`)
  - IDE/Editor files: `.vscode/`, `.idea/`, `*.swp`, `*.swo`, `*.swn`, `.DS_Store`, `*.sublime-*`
  - Testing artifacts: `.pytest_cache/`, `.coverage`, `htmlcov/`, `.tox/`, `.mypy_cache/`
  - Build artifacts: `*.egg-info/`, `dist/`, `build/`, `*.whl`
  - OS files: `Thumbs.db`, `.DS_Store`
  - IDE: `*.iml`, `.idea/**`, `.vscode/**`
  - Local environment: `.env`, `.env.local`
  - Test reports: `reports/` (generated, not checked in)
  - Database files: `*.db`, `*.sqlite`, `*.sqlite3`
  - Logs: `*.log`, `logs/`
  - Secrets: `secrets/`, `*.pem`, `*.key`
  - Temporary files: `tmp/`, `temp/`, `.tmp`
- **Repository Hygiene**: No credentials, API keys, or sensitive data committed
- **Commit Hygiene**: Clear, descriptive commit messages following conventional commits format

### 18.4 Documentation
- **README.md**: Project overview, setup instructions, running tests
- **API Documentation**: Auto-generated Swagger UI (`/docs`) and ReDoc (`/redoc`)
- **Configuration**: Document all environment variables and configuration options
- **Architecture**: Architecture decision records (ADRs) for major decisions
- **CHANGELOG**: Track version releases and breaking changes

### 18.5 Operational Readiness
- **Health Checks**: Kubernetes-compatible liveness and readiness probes
- **Graceful Shutdown**: Allow in-flight requests to complete before shutdown (configurable timeout)
- **Resource Monitoring**: CPU, memory, and disk usage tracking
- **Log Aggregation**: Structured JSON logs for easy parsing by log aggregation tools
- **Tracing**: Correlation IDs propagated across service boundaries

---

**End of Document**
