"""Integration tests for RabbitMQ consumer + AnalyticsOrchestrator.

These tests verify that:
- The message handler created by `internal.consumers.main.create_message_handler`
  can process a synthetic message referencing a MinIO-stored JSON (via a fake
  `MinioAdapter`).
- The orchestrator runs end-to-end and calls the analytics repository with a
  `PostAnalytics`-shaped payload (without requiring a real database).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest  # type: ignore


class FakeProcessContext:
    """Async context manager mimicking aio_pika message.process()."""

    def __init__(self, message: "FakeIncomingMessage") -> None:
        self._message = message

    async def __aenter__(self) -> "FakeIncomingMessage":
        return self._message

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        # No-op for tests; in real aio_pika this would ack/nack
        return None


class FakeIncomingMessage:
    """Minimal IncomingMessage replacement for testing."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def process(self) -> FakeProcessContext:
        """Return async context manager for `async with message.process():`."""
        return FakeProcessContext(self)


def _make_sample_post() -> Dict[str, Any]:
    """Create a sample Atomic JSON post."""
    return {
        "meta": {
            "id": "consumer_post_1",
            "project_id": "11111111-1111-1111-1111-111111111111",
            "platform": "facebook",
            "published_at": datetime.now(timezone.utc).isoformat(),
        },
        "content": {
            "text": "Xe đẹp nhưng giá hơi cao",
            "transcription": "",
        },
        "interaction": {
            "views": 1000,
            "likes": 100,
            "comments_count": 10,
            "shares": 5,
            "saves": 3,
        },
        "author": {
            "id": "user_1",
            "name": "Test User",
            "followers": 2000,
            "is_verified": False,
        },
        "comments": [
            {"text": "đẹp quá", "likes": 5},
            {"text": "giá hơi chát", "likes": 3},
        ],
    }


class TestConsumerIntegration:
    """Integration tests for consumer message handler."""

    def test_consumer_processes_event_and_calls_repository(self, monkeypatch) -> None:
        """Message handler should process data.collected event and call repository.save."""
        # Prepare fake MinIO adapter
        sample_post = _make_sample_post()

        class FakeMinioAdapter:
            def download_json(self, bucket: str, object_path: str) -> Dict[str, Any]:
                return [sample_post]  # Return as batch (list)

            def download_batch(self, bucket: str, object_path: str) -> List[Dict[str, Any]]:
                return [sample_post]

        # Patch consumer module to use fake MinIO and fake repository
        import internal.consumers.main as consumer_main
        import services.analytics.orchestrator as orchestrator_module

        monkeypatch.setattr(consumer_main, "MinioAdapter", lambda: FakeMinioAdapter())

        # Patch IntentClassifier inside orchestrator to return dicts as expected
        class FakeIntentClassifier:
            def predict(self, text: str) -> Dict[str, Any]:
                return {"intent": "DISCUSSION", "confidence": 1.0, "should_skip": False}

        monkeypatch.setattr(orchestrator_module, "IntentClassifier", FakeIntentClassifier)

        saved: List[Dict[str, Any]] = []

        class FakeRepository:
            def __init__(self, db: Any) -> None:  # db is unused
                self.db = db

            def save(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
                saved.append(analytics_data)
                return analytics_data

        class FakeErrorRepository:
            def __init__(self, db: Any) -> None:
                self.db = db

            def save(self, error_data: Dict[str, Any]) -> Dict[str, Any]:
                return error_data

        monkeypatch.setattr(consumer_main, "AnalyticsRepository", FakeRepository)
        monkeypatch.setattr(consumer_main, "CrawlErrorRepository", FakeErrorRepository)

        # Create message handler with no AI models (sentiment will degrade gracefully)
        handler = consumer_main.create_message_handler(phobert=None, spacyyake=None)

        # Build synthetic data.collected event envelope
        envelope = {
            "event_id": "evt_test_001",
            "event_type": "data.collected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "minio_path": "test-bucket/posts/post_1.json",
                "project_id": "11111111-1111-1111-1111-111111111111",
                "job_id": "proj_test-brand-0",
                "batch_index": 0,
                "content_count": 1,
                "platform": "facebook",
            },
        }
        body = json.dumps(envelope).encode("utf-8")
        message = FakeIncomingMessage(body)

        # Run handler in event loop
        asyncio.run(handler(message))

        # Verify repository.save was called with expected payload
        assert len(saved) == 1
        analytics = saved[0]
        assert analytics["id"] == sample_post["meta"]["id"]
        assert analytics["platform"] == "FACEBOOK"
        assert "impact_score" in analytics
        assert "risk_level" in analytics
