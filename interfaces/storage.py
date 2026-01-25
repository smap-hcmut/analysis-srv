"""Storage interface - Abstract base class for object storage."""

from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


class IStorage(ABC):
    """Interface for object storage operations (MinIO, S3, etc.)."""

    @abstractmethod
    async def upload(
        self,
        bucket: str,
        object_name: str,
        data: BinaryIO,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload an object to storage."""
        pass

    @abstractmethod
    async def download(self, bucket: str, object_name: str) -> bytes:
        """Download an object from storage."""
        pass

    @abstractmethod
    async def delete(self, bucket: str, object_name: str) -> bool:
        """Delete an object from storage."""
        pass

    @abstractmethod
    async def exists(self, bucket: str, object_name: str) -> bool:
        """Check if an object exists."""
        pass

    @abstractmethod
    async def get_url(self, bucket: str, object_name: str, expires: int = 3600) -> str:
        """Get a presigned URL for an object."""
        pass
