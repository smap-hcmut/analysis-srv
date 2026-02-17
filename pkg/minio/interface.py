"""Interface for object storage operations."""

from typing import Dict, List, Optional, Protocol, Union, runtime_checkable

from .type import UploadResult


@runtime_checkable
class IObjectStorage(Protocol):
    """Protocol for object storage operations.

    Implementations are safe for concurrent use.
    """

    def download_json(
        self, bucket: str, object_path: str
    ) -> Union[Dict[str, object], List[Dict[str, object]]]:
        """Download and parse a JSON object."""
        ...

    def download_batch(self, bucket: str, object_path: str) -> List[Dict[str, object]]:
        """Download a batch of items."""
        ...

    def upload_json(
        self,
        bucket: str,
        object_path: str,
        data: Dict[str, object],
        compress: bool = True,
    ) -> UploadResult:
        """Upload a JSON object with optional compression."""
        ...

    def object_exists(self, bucket: str, object_path: str) -> bool:
        """Check if object exists."""
        ...


__all__ = ["IObjectStorage"]
