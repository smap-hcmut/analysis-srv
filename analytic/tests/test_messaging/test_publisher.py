"""Unit tests for RabbitMQ publisher.

Tests the RabbitMQPublisher class for result publishing functionality.
Uses mocks to avoid requiring actual RabbitMQ connection.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.messaging.publisher import (
    RabbitMQPublisher,
    RabbitMQPublisherError,
)
from models.messages import (
    AnalyzeResultPayload,
    create_success_result,
    create_error_result,
)


@pytest.fixture
def mock_channel():
    """Create a mock RabbitMQ channel."""
    channel = AsyncMock()
    channel.declare_exchange = AsyncMock()
    return channel


@pytest.fixture
def mock_exchange():
    """Create a mock RabbitMQ exchange."""
    exchange = AsyncMock()
    exchange.publish = AsyncMock()
    return exchange


class TestRabbitMQPublisherInit:
    """Tests for RabbitMQPublisher initialization."""

    def test_init_with_defaults(self, mock_channel):
        """Test initialization with default config values."""
        publisher = RabbitMQPublisher(channel=mock_channel)

        assert publisher.channel == mock_channel
        assert publisher.exchange_name == "results.inbound"
        assert publisher.routing_key == "analyze.result"
        assert publisher.exchange is None
        assert publisher._is_setup is False

    def test_init_with_custom_values(self, mock_channel):
        """Test initialization with custom exchange and routing key."""
        publisher = RabbitMQPublisher(
            channel=mock_channel,
            exchange_name="custom.exchange",
            routing_key="custom.routing",
        )

        assert publisher.exchange_name == "custom.exchange"
        assert publisher.routing_key == "custom.routing"

    def test_is_ready_before_setup(self, mock_channel):
        """Test is_ready returns False before setup."""
        publisher = RabbitMQPublisher(channel=mock_channel)
        assert publisher.is_ready() is False


class TestRabbitMQPublisherSetup:
    """Tests for RabbitMQPublisher.setup() method."""

    @pytest.mark.asyncio
    async def test_setup_declares_exchange(self, mock_channel, mock_exchange):
        """Test setup declares a durable topic exchange."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        mock_channel.declare_exchange.assert_called_once()
        call_args = mock_channel.declare_exchange.call_args
        assert call_args[0][0] == "results.inbound"  # exchange name
        assert publisher.exchange == mock_exchange
        assert publisher._is_setup is True
        assert publisher.is_ready() is True

    @pytest.mark.asyncio
    async def test_setup_idempotent(self, mock_channel, mock_exchange):
        """Test setup is idempotent - calling twice doesn't redeclare."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()
        await publisher.setup()  # Second call

        # Should only be called once
        assert mock_channel.declare_exchange.call_count == 1

    @pytest.mark.asyncio
    async def test_setup_error_handling(self, mock_channel):
        """Test setup raises RabbitMQPublisherError on failure."""
        mock_channel.declare_exchange.side_effect = Exception("Connection failed")

        publisher = RabbitMQPublisher(channel=mock_channel)

        with pytest.raises(RabbitMQPublisherError) as exc_info:
            await publisher.setup()

        assert "Failed to setup publisher" in str(exc_info.value)
        assert publisher._is_setup is False


class TestRabbitMQPublisherPublish:
    """Tests for RabbitMQPublisher.publish() method."""

    @pytest.mark.asyncio
    async def test_publish_requires_setup(self, mock_channel):
        """Test publish raises error if not setup."""
        publisher = RabbitMQPublisher(channel=mock_channel)

        with pytest.raises(RabbitMQPublisherError) as exc_info:
            await publisher.publish({"test": "message"})

        assert "not setup" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_publish_message(self, mock_channel, mock_exchange):
        """Test publishing a message."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        message = {"project_id": "proj_123", "job_id": "test", "task_type": "analyze_result"}
        await publisher.publish(message)

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args

        # Verify message was serialized
        published_message = call_args[0][0]
        assert published_message.body == json.dumps(message, ensure_ascii=False).encode("utf-8")

        # Verify routing key
        assert call_args[1]["routing_key"] == "analyze.result"

    @pytest.mark.asyncio
    async def test_publish_with_custom_routing_key(self, mock_channel, mock_exchange):
        """Test publishing with custom routing key."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        await publisher.publish({"test": "message"}, routing_key="custom.key")

        call_args = mock_exchange.publish.call_args
        assert call_args[1]["routing_key"] == "custom.key"

    @pytest.mark.asyncio
    async def test_publish_error_handling(self, mock_channel, mock_exchange):
        """Test publish raises RabbitMQPublisherError on failure."""
        mock_channel.declare_exchange.return_value = mock_exchange
        mock_exchange.publish.side_effect = Exception("Publish failed")

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        with pytest.raises(RabbitMQPublisherError) as exc_info:
            await publisher.publish({"test": "message"})

        assert "Failed to publish message" in str(exc_info.value)


class TestRabbitMQPublisherPublishAnalyzeResult:
    """Tests for RabbitMQPublisher.publish_analyze_result() method."""

    @pytest.mark.asyncio
    async def test_publish_analyze_result_flat_payload(self, mock_channel, mock_exchange):
        """Test publishing AnalyzeResultPayload produces flat JSON."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        payload = create_success_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )

        await publisher.publish_analyze_result(payload)

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        published_body = call_args[0][0].body
        parsed = json.loads(published_body.decode("utf-8"))

        # Verify flat format (no wrapper)
        assert "success" not in parsed
        assert "payload" not in parsed
        assert parsed["project_id"] == "proj_123"
        assert parsed["job_id"] == "proj_123-brand-0"
        assert parsed["task_type"] == "analyze_result"
        assert parsed["batch_size"] == 50
        assert parsed["success_count"] == 48
        assert parsed["error_count"] == 2
        # Internal fields excluded
        assert "results" not in parsed
        assert "errors" not in parsed

    @pytest.mark.asyncio
    async def test_publish_analyze_result_with_flat_dict(self, mock_channel, mock_exchange):
        """Test publishing flat dictionary message."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        msg_dict = {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 48,
            "error_count": 2,
        }

        await publisher.publish_analyze_result(msg_dict)

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        published_body = call_args[0][0].body
        parsed = json.loads(published_body.decode("utf-8"))

        assert parsed == msg_dict

    @pytest.mark.asyncio
    async def test_publish_analyze_result_empty_project_id_rejected(
        self, mock_channel, mock_exchange
    ):
        """Test publishing with empty project_id raises error."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        payload = AnalyzeResultPayload(
            project_id="",  # Empty
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )

        with pytest.raises(RabbitMQPublisherError) as exc_info:
            await publisher.publish_analyze_result(payload)

        assert "project_id is required" in str(exc_info.value)
        mock_exchange.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_analyze_result_none_project_id_in_dict_rejected(
        self, mock_channel, mock_exchange
    ):
        """Test publishing dict with None project_id raises error."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        msg_dict = {
            "project_id": None,
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 48,
            "error_count": 2,
        }

        with pytest.raises(RabbitMQPublisherError) as exc_info:
            await publisher.publish_analyze_result(msg_dict)

        assert "project_id is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_analyze_result_invalid_type(self, mock_channel, mock_exchange):
        """Test publishing invalid message type raises error."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        with pytest.raises(RabbitMQPublisherError) as exc_info:
            await publisher.publish_analyze_result("invalid string")

        assert "Invalid message type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_analyze_result_error_handling(self, mock_channel, mock_exchange):
        """Test publish_analyze_result handles publish errors."""
        mock_channel.declare_exchange.return_value = mock_exchange
        mock_exchange.publish.side_effect = Exception("Network error")

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        payload = create_success_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            success_count=48,
            error_count=2,
        )

        with pytest.raises(RabbitMQPublisherError):
            await publisher.publish_analyze_result(payload)

    @pytest.mark.asyncio
    async def test_publish_error_result_flat(self, mock_channel, mock_exchange):
        """Test publishing error result produces flat JSON."""
        mock_channel.declare_exchange.return_value = mock_exchange

        publisher = RabbitMQPublisher(channel=mock_channel)
        await publisher.setup()

        payload = create_error_result(
            project_id="proj_123",
            job_id="proj_123-brand-0",
            batch_size=50,
            error_message="MinIO fetch failed",
        )

        await publisher.publish_analyze_result(payload)

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        published_body = call_args[0][0].body
        parsed = json.loads(published_body.decode("utf-8"))

        # Verify flat format
        assert parsed == {
            "project_id": "proj_123",
            "job_id": "proj_123-brand-0",
            "task_type": "analyze_result",
            "batch_size": 50,
            "success_count": 0,
            "error_count": 50,
        }
        # No errors array in output
        assert "errors" not in parsed
