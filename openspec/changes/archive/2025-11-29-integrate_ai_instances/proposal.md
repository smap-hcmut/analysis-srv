# Integrate AI Model Instances

**Change ID**: `integrate_ai_instances`
**Status**: Proposal
**Created**: 2025-11-29
**Author**: Analytics Engine Team

---

## Why

The Analytics Engine has PhoBERT ONNX and SpaCy-YAKE models implemented and tested in isolation, but they are not accessible in the API or Consumer services. This change integrates the AI models into the service lifecycle using FastAPI's lifespan pattern and dependency injection, enabling:

1. **Production-ready API**: Models loaded once at startup and reused across all requests
2. **Consumer service integration**: AI models available for message queue processing
3. **Test endpoint**: Validate the full analytics pipeline with real JSON input
4. **Development efficiency**: Fast feedback loop for testing model integration

This unblocks the analytics pipeline by making AI models available to both API endpoints and background message processing.

---

## Problem Statement

Currently, PhoBERT ONNX and SpaCy-YAKE models have been implemented and tested in isolation, but they are not integrated into the API and Consumer service lifecycles. There is no way to:

1. Initialize AI model instances once and reuse them across requests (avoiding expensive model loading on every request)
2. Test the full analytics pipeline with real JSON input data
3. Validate that the models work correctly when integrated into the service architecture

This creates a gap between isolated model testing and production-ready service integration.

## Proposed Solution

Integrate AI model instances (PhoBERT ONNX and SpaCy-YAKE) into the Analytics Engine services using:

1. **Lifespan Context Manager**: Initialize models once during application startup
2. **Dependency Injection**: Provide model instances to services via constructor injection
3. **Test API Endpoint**: Create `/api/v1/test/analytics` endpoint to validate full pipeline with JSON input

### Key Design Decisions

**Why Lifespan + Dependency Injection?**
- **Performance**: Models loaded once, reused for all requests (~2-5s startup vs 50-200ms per request)
- **Testability**: Easy to mock AI instances in unit tests
- **FastAPI Best Practice**: Standard pattern for managing application state
- **Resource Management**: Proper cleanup on shutdown

**Why Test Endpoint?**
- **Development**: Validate JSON input format and pipeline integration
- **Debugging**: See full analytics output (preprocessing → keywords → sentiment)
- **Documentation**: Living example of expected input/output format

---

## Scope

### In Scope
- ✅ Initialize PhoBERT ONNX in API service lifespan
- ✅ Initialize SpaCy-YAKE in API service lifespan
- ✅ Initialize PhoBERT ONNX in Consumer service lifespan
- ✅ Initialize SpaCy-YAKE in Consumer service lifespan
- ✅ Create dependency injection pattern for model access
- ✅ Implement test endpoint `/api/v1/test/analytics` (POST)
- ✅ Validate JSON input schema
- ✅ Return full analytics debug response

### Out of Scope
- ❌ TextPreprocessor implementation (separate proposal)
- ❌ Full pipeline orchestration (separate proposal)
- ❌ Production analytics processing (separate proposal)
- ❌ Database persistence (future work)

---

## Technical Design

### 1. Service Lifecycle Integration

**File**: `commands/api/main.py`

```python
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage AI model lifecycle."""
    try:
        logger.info("Loading AI models...")
        
        # Initialize models (expensive operation, done once)
        app.state.phobert = PhoBERTONNX()
        app.state.spacyyake = SpacyYakeExtractor()
        
        logger.info("AI models loaded successfully")
        yield
        
        # Cleanup
        logger.info("Shutting down AI models...")
        del app.state.phobert
        del app.state.spacyyake
        
    except Exception as e:
        logger.error(f"Failed to initialize AI models: {e}")
        raise
```

### 2. Infrastructure Layer: RabbitMQ Client

**File**: `infrastructure/messaging/rabbitmq.py` (NEW)

```python
import aio_pika
import asyncio
from typing import Optional, Callable, Awaitable
from core.logger import logger
from core.config import settings

class RabbitMQClient:
    """
    Infrastructure wrapper for RabbitMQ operations.
    Handles connection management, channel creation, and message consumption.
    """
    def __init__(self, url: str):
        self.url = url
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        
    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            logger.info(f"Connecting to RabbitMQ at {self.url}...")
            self.connection = await aio_pika.connect_robust(self.url)
            self.channel = await self.connection.channel()
            # Set QoS to process 1 message at a time per worker
            await self.channel.set_qos(prefetch_count=1)
            logger.info("Connected to RabbitMQ successfully")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def close(self) -> None:
        """Close connection gracefully."""
        if self.connection:
            logger.info("Closing RabbitMQ connection...")
            await self.connection.close()
            logger.info("RabbitMQ connection closed")

    async def consume(self, queue_name: str, callback: Callable[[aio_pika.IncomingMessage], Awaitable[None]]) -> None:
        """
        Start consuming messages from a queue.
        
        Args:
            queue_name: Name of the queue to consume from
            callback: Async function to handle messages
        """
        if not self.channel:
            raise RuntimeError("RabbitMQ channel not initialized. Call connect() first.")
            
        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.consume(callback)
        logger.info(f"Started consuming from queue: {queue_name}")
```

### 3. Consumer Service Integration

**File**: `commands/consumer/main.py`

```python
import asyncio
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from infrastructure.messaging.rabbitmq import RabbitMQClient
from core.logger import logger
from core.config import settings

# Global instances
phobert: PhoBERTONNX = None
spacyyake: SpacyYakeExtractor = None
rabbitmq: RabbitMQClient = None

async def main():
    """Entry point for the Analytics Engine consumer."""
    global phobert, spacyyake, rabbitmq
    
    try:
        logger.info("Starting Consumer service...")
        
        # 1. Initialize AI models
        logger.info("Loading AI models...")
        phobert = PhoBERTONNX()
        spacyyake = SpacyYakeExtractor()
        logger.info("AI models loaded successfully")
        
        # 2. Initialize Infrastructure
        rabbitmq = RabbitMQClient(settings.rabbitmq_url)
        await rabbitmq.connect()
        
        # 3. Start consuming messages
        # Pass models to the handler wrapper
        from internal.consumers.handler import create_message_handler
        
        handler = create_message_handler(phobert, spacyyake)
        await rabbitmq.consume(settings.queue_name, handler)
        
        # Keep running
        await asyncio.Future()
        
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Consumer error: {e}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down Consumer service...")
        
        if rabbitmq:
            await rabbitmq.close()
            
        if phobert: del phobert
        if spacyyake: del spacyyake
        
        logger.info("Consumer service stopped")
```

### 2. Dependency Injection Pattern

**File**: `internal/api/dependencies.py` (NEW)

```python
from fastapi import Depends, Request
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor

def get_phobert(request: Request) -> PhoBERTONNX:
    """Dependency injection for PhoBERT model."""
    return request.app.state.phobert

def get_spacyyake(request: Request) -> SpacyYakeExtractor:
    """Dependency injection for SpaCy-YAKE model."""
    return request.app.state.spacyyake
```

### 3. Test API Endpoint

**File**: `internal/api/routes/test.py` (NEW)

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from internal.api.dependencies import get_phobert, get_spacyyake
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor

router = APIRouter(prefix="/api/v1/test", tags=["testing"])

class AnalyticsTestRequest(BaseModel):
    """Test request matching master-proposal.md JSON format."""
    meta: Dict[str, Any]
    content: Dict[str, Any]
    interaction: Dict[str, Any]
    author: Dict[str, Any]
    comments: List[Dict[str, Any]]

class AnalyticsTestResponse(BaseModel):
    """Full analytics debug response."""
    post_id: str
    preprocessing: Dict[str, Any]
    keywords: Dict[str, Any]
    sentiment: Dict[str, Any]
    metadata: Dict[str, Any]

@router.post("/analytics", response_model=AnalyticsTestResponse)
async def test_analytics(
    request: AnalyticsTestRequest,
    phobert: PhoBERTONNX = Depends(get_phobert),
    spacyyake: SpacyYakeExtractor = Depends(get_spacyyake)
):
    """
    Test endpoint for analytics pipeline.
    
    Accepts JSON input matching master-proposal.md format and returns
    full analytics output for debugging.
    """
    try:
        # Extract post ID
        post_id = request.meta.get("id", "unknown")
        
        # For now, just validate models are accessible
        # Full processing will be implemented in future proposals
        
        return AnalyticsTestResponse(
            post_id=post_id,
            preprocessing={
                "status": "not_implemented",
                "message": "Preprocessing will be implemented in next proposal"
            },
            keywords={
                "status": "models_loaded",
                "spacyyake_available": spacyyake is not None
            },
            sentiment={
                "status": "models_loaded",
                "phobert_available": phobert is not None
            },
            metadata={
                "platform": request.meta.get("platform"),
                "language": request.meta.get("lang"),
                "models_initialized": True
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 4. Router Registration

**File**: `internal/api/main.py`

```python
from internal.api.routes import test

# Register test router
app.include_router(test.router)
```

---

## Success Criteria

### Functional Requirements
- [ ] PhoBERT model initializes successfully on API startup
- [ ] SpaCy-YAKE model initializes successfully on API startup
- [ ] PhoBERT model initializes successfully on Consumer startup
- [ ] SpaCy-YAKE model initializes successfully on Consumer startup
- [ ] Models are accessible via dependency injection (API)
- [ ] Models are passed to message handlers (Consumer)
- [ ] Test endpoint accepts JSON matching master-proposal.md format
- [ ] Test endpoint returns full analytics debug response
- [ ] Startup time < 10 seconds (model loading)
- [ ] Test endpoint response time < 1 second

### Non-Functional Requirements
- [ ] Models loaded once, not per-request
- [ ] Proper error handling for model initialization failures
- [ ] Logging for model lifecycle events
- [ ] API documentation (OpenAPI/Swagger) generated automatically
- [ ] Unit tests for dependency injection
- [ ] Integration tests for test endpoint

---

## Implementation Plan

See `tasks.md` for detailed breakdown.

**Estimated Effort**: 5-7 hours

---

## Dependencies

### Required
- ✅ PhoBERT ONNX implementation (`infrastructure/ai/phobert_onnx.py`)
- ✅ SpaCy-YAKE implementation (`infrastructure/ai/spacyyake_extractor.py`)
- ✅ FastAPI application structure

### Blocked By
- None

### Blocks
- TextPreprocessor integration (future proposal)
- Full analytics pipeline (future proposal)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model loading fails on startup | High | Implement retry logic + fallback mode |
| Memory usage too high | Medium | Monitor memory, consider lazy loading |
| Startup time too slow | Low | Acceptable for dev/test, optimize later |

---

## Alternatives Considered

### Alternative 1: Singleton Pattern
**Rejected**: Less testable, not FastAPI idiomatic

### Alternative 2: Lazy Loading
**Rejected**: First request would be slow, unpredictable latency

### Alternative 3: Separate Model Service
**Rejected**: Over-engineering for current scale

---

## References

- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Dependency Injection in FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/)
- PhoBERT Integration: `openspec/changes/archive/2025-11-29-phobert_integration/`
- SpaCy-YAKE Integration: `openspec/changes/archive/2025-11-29-spacy_yake_integration/`
- Master Proposal: `documents/master-proposal.md`
