import abc
from typing import Optional, Dict, Any, List
from app.models import (
    ChannelEnum,
    NotificationStatusEnum,
    ChannelStatus,
)


class BaseProvider(abc.ABC):
    """Abstract base class for all notification providers"""

    def __init__(self, channel: ChannelEnum):
        self.channel = channel

    @abc.abstractmethod
    async def send(self, recipient: str, subject: Optional[str] = None, body: Optional[str] = None,
                   template_variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send notification through the provider
        
        Returns dict with:
        - success: bool
        - provider_reference: str (optional)
        - error_code: str (optional)
        - error_message: str (optional)
        """
        pass

    @abc.abstractmethod
    async def test_connection(self) -> bool:
        """Test provider connectivity"""
        pass

    @abc.abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get provider health status"""
        pass
