"""MinIO storage adapter for reading Atomic JSON posts.

This module wraps the MinIO Python SDK behind a small adapter so that
callers (e.g. orchestrated consumers) can fetch JSON objects from MinIO
without depending directly on the SDK.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from minio import Minio  # type: ignore

from core.config import settings
from core.logger import logger


class MinioAdapter:
    """Thin wrapper around MinIO client to download JSON objects."""

    def __init__(self) -> None:
        self._client = Minio(
            settings.minio_endpoint.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_endpoint.startswith("https://"),
        )

    def download_json(self, bucket: str, object_path: str) -> Dict[str, Any]:
        """Download and parse a JSON object from MinIO.

        This method streams the object from MinIO and parses it directly
        into a Python dict without writing temporary files.

        Raises:
            RuntimeError: If the object cannot be fetched or parsed.
        """
        logger.info("Downloading JSON from MinIO bucket=%s, path=%s", bucket, object_path)
        try:
            response = self._client.get_object(bucket, object_path)
            try:
                # `response` is a stream; json.load will read it fully.
                data = json.load(response)
            finally:
                response.close()
                response.release_conn()
            if not isinstance(data, dict):
                raise RuntimeError("Expected JSON object (dict) from MinIO")
            return data
        except Exception as exc:  # pragma: no cover - I/O heavy path
            logger.error("Failed to fetch JSON from MinIO: %s", exc)
            raise RuntimeError(f"Failed to fetch from MinIO: {exc}") from exc
