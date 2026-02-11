"""Consumer package for analytics service.

This package contains:
- Dependencies: Struct holding all service dependencies
- IConsumerServer: Protocol interface for consumer server
- ConsumerServer: Implementation of consumer server
- MessageHandler: Handler for processing messages
"""

from .type import Dependencies
from .interface import IConsumerServer
from .server import ConsumerServer
from .handler import MessageHandler

__all__ = [
    "Dependencies",
    "IConsumerServer",
    "ConsumerServer",
    "MessageHandler",
]
