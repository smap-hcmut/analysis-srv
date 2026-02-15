DEFAULT_QUEUE_NAME = "analytics_queue"
DEFAULT_PREFETCH_COUNT = 1
DEFAULT_DURABLE = True

# Exchange Types
EXCHANGE_TYPE_TOPIC = "topic"
EXCHANGE_TYPE_DIRECT = "direct"
EXCHANGE_TYPE_FANOUT = "fanout"

# Errors
ERROR_URL_EMPTY = "url cannot be empty"
ERROR_QUEUE_NAME_EMPTY = "queue_name cannot be empty"
ERROR_PREFETCH_COUNT_POSITIVE = "prefetch_count must be positive, got {count}"
ERROR_EXCHANGE_NAME_EMPTY = "exchange_name cannot be empty"
ERROR_ROUTING_KEY_EMPTY = "routing_key cannot be empty"
ERROR_AIO_PIKA_NOT_INSTALLED = (
    "aio-pika is required for RabbitMQ support. Install with: pip install aio-pika"
)
ERROR_PUBLISHER_NOT_SETUP = "Publisher not setup. Call setup() first."
ERROR_INVALID_MESSAGE_TYPE = (
    "Invalid message type: {type}. Expected MessagePayload or dict."
)
ERROR_PROJECT_ID_REQUIRED = (
    "project_id is required for publishing analyze results. "
    "Collector will reject messages without project_id."
)
