import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
import redis
from app.config import settings
from app.models import Notification

logger = logging.getLogger(__name__)


class RedisQueue:
    """Redis-based queue for async notification processing"""

    def __init__(self):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
        self.notification_queue_key = "notifications:queue"
        self.retry_queue_key = "notifications:retry"
        self.dead_letter_queue_key = "notifications:dlq"
        self.processing_queue_key = "notifications:processing"

    async def enqueue(self, notification: Notification) -> bool:
        """Add notification to queue"""
        try:
            notification_json = json.dumps(
                {
                    "id": str(notification.id),
                    "tenant_id": str(notification.tenant_id),
                    "user_id": str(notification.user_id),
                    "notification_type": notification.notification_type.value,
                    "channels_requested": [c.value for c in notification.channels_requested],
                    "status": notification.status.value,
                    "priority": notification.priority.value,
                    "template_id": str(notification.template_id),
                    "template_version": notification.template_version,
                    "template_variables": notification.template_variables,
                    "recipient": notification.recipient.model_dump(),
                    "correlation_id": str(notification.correlation_id),
                    "created_at": notification.created_at.isoformat(),
                }
            )
            self.redis_client.rpush(self.notification_queue_key, notification_json)
            logger.info(f"Enqueued notification: {notification.id}")
            return True
        except Exception as e:
            logger.error(f"Error enqueuing notification: {e}")
            return False

    async def dequeue(self, batch_size: int = 1) -> List[Dict[str, Any]]:
        """Dequeue notifications for processing"""
        try:
            notifications = []
            for _ in range(batch_size):
                notification_json = self.redis_client.lpop(self.notification_queue_key)
                if not notification_json:
                    break
                notification_data = json.loads(notification_json)
                notifications.append(notification_data)
            logger.info(f"Dequeued {len(notifications)} notifications")
            return notifications
        except Exception as e:
            logger.error(f"Error dequeuing notifications: {e}")
            return []

    async def enqueue_retry(self, notification_id: str, delay_seconds: int = 0) -> bool:
        """Add notification to retry queue with optional delay"""
        try:
            self.redis_client.rpush(self.retry_queue_key, notification_id)
            if delay_seconds > 0:
                self.redis_client.expire(self.retry_queue_key, delay_seconds)
            logger.info(f"Enqueued retry for notification: {notification_id}")
            return True
        except Exception as e:
            logger.error(f"Error enqueuing retry: {e}")
            return False

    async def enqueue_dead_letter(self, notification_id: str, reason: str = "") -> bool:
        """Move notification to dead letter queue"""
        try:
            dead_letter_data = json.dumps({
                "notification_id": notification_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self.redis_client.rpush(self.dead_letter_queue_key, dead_letter_data)
            logger.warning(f"Moved notification to DLQ: {notification_id}, reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Error enqueuing dead letter: {e}")
            return False

    async def get_queue_depth(self) -> int:
        """Get number of pending notifications in queue"""
        try:
            depth = self.redis_client.llen(self.notification_queue_key)
            return depth
        except Exception as e:
            logger.error(f"Error getting queue depth: {e}")
            return 0

    async def get_retry_queue_depth(self) -> int:
        """Get number of notifications in retry queue"""
        try:
            depth = self.redis_client.llen(self.retry_queue_key)
            return depth
        except Exception as e:
            logger.error(f"Error getting retry queue depth: {e}")
            return 0

    async def get_dlq_depth(self) -> int:
        """Get number of notifications in dead letter queue"""
        try:
            depth = self.redis_client.llen(self.dead_letter_queue_key)
            return depth
        except Exception as e:
            logger.error(f"Error getting DLQ depth: {e}")
            return 0

    async def health_check(self) -> bool:
        """Check Redis connectivity"""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def set_cache(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Store value in cache with TTL"""
        try:
            self.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False

    def get_cache(self, key: str) -> Optional[str]:
        """Retrieve value from cache"""
        try:
            return self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Error getting cache: {e}")
            return None

    def delete_cache(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False

