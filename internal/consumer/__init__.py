"""Consumer package for analytics service.

This package contains:
- Dependencies: Struct holding all service dependencies
- IConsumerServer: Protocol interface for consumer server
- ConsumerServer: Consumer server with multi-queue support
"""

from .type import Dependencies
from .interface import IConsumerServer
from .server import ConsumerServer

__all__ = [
    "Dependencies",
    "IConsumerServer",
    "ConsumerServer",
]
