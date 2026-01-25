## Context

Analytics Engine hiện tại chỉ có Consumer service để xử lý events từ Crawler. Dashboard frontend cần REST API để truy xuất dữ liệu đã phân tích. API service này sẽ là read-only layer, serve data từ PostgreSQL tables đã được populate bởi Analytics pipeline.

Constraints:
- Sử dụng existing database schema (post_analytics, crawl_errors)
- Follow Clean Architecture patterns đã established
- Performance requirement: <100ms response time for list queries
- Filtering requirement: Support project_id (required), brand_name, keyword filtering

## Goals / Non-Goals

### Goals:
- RESTful API với 8 endpoints theo API design proposal
- Standardized response format với success/error handling
- Comprehensive filtering, sorting, pagination
- Auto-generated Swagger documentation
- Repository pattern cho data access abstraction
- High performance queries với database indexes

### Non-Goals:
- Write operations (API chỉ read-only)
- Real-time subscriptions/WebSockets
- Authentication/authorization (để lại cho API Gateway)
- Data transformation (dùng dữ liệu đã processed)

## Decisions

### Architecture Pattern
**Decision**: Sử dụng existing Clean Architecture với thêm API layer
- `command/api/` - Entry point với Uvicorn
- `internal/api/` - FastAPI app và route registration  
- `repository/` - Data access layer với abstract interfaces
- `models/schemas/` - Pydantic schemas cho API DTOs

**Alternatives considered**: 
- Separate microservice: Phức tạp hơn, không cần thiết hiện tại
- Direct SQLAlchemy in routes: Vi phạm separation of concerns

### Database Access Pattern
**Decision**: Repository pattern với async SQLAlchemy
```python
# interfaces/analytics_repository.py
class IAnalyticsRepository(ABC):
    async def get_posts(self, filters: PostFilters) -> PaginatedResult[PostAnalytics]
    async def get_post_by_id(self, post_id: str) -> Optional[PostAnalytics]

# repository/analytics_repository.py
class AnalyticsRepository(IAnalyticsRepository):
    async def get_posts(self, filters):
        # Implement với SQLAlchemy async queries
```

**Alternatives considered**: 
- Direct ORM usage: Khó test, tight coupling
- Raw SQL: Mất type safety, khó maintain

### Response Format Standardization
**Decision**: Unified response wrapper với meta information
```python
{
  "success": true,
  "data": {...},
  "pagination": {...},  # if applicable
  "meta": {
    "timestamp": "2025-12-19T10:30:00Z",
    "request_id": "req_abc123",
    "version": "v1"
  }
}
```

### Error Handling Strategy
**Decision**: Global exception handler với application-specific error codes
```python
# Application error codes
VAL_001: Validation error
VAL_002: Invalid format  
VAL_003: Required field missing
RES_001: Resource not found
SYS_001: Internal error
```

**Alternatives considered**:
- HTTP status only: Không đủ granularity cho debugging
- Exception propagation: Expose internal details

### Database Query Optimization
**Decision**: Strategic indexing cho common query patterns
```sql
-- Composite indexes cho filter combinations
CREATE INDEX idx_post_analytics_project_brand ON post_analytics(project_id, brand_name);
CREATE INDEX idx_post_analytics_project_brand_keyword ON post_analytics(project_id, brand_name, keyword);
CREATE INDEX idx_post_analytics_published_at ON post_analytics(published_at);
```

**Query patterns**:
- Offset-based pagination (simple, predictable performance)
- Lazy loading cho relationships không critical
- JSONB aggregation cho top-keywords endpoint

## Risks / Trade-offs

### Performance Risk
- **Risk**: Slow queries với large datasets
- **Mitigation**: Database indexes, query optimization, pagination limits (max 100 items)

### Schema Coupling
- **Risk**: API schema tightly coupled với database schema
- **Mitigation**: Pydantic schemas làm transformation layer, abstract database details

### JSON Aggregation Complexity
- **Risk**: Top-keywords endpoint có thể chậm với JSONB queries
- **Mitigation**: PostgreSQL JSONB functions, fallback về application-layer aggregation

## Migration Plan

### Phase 1: Core Infrastructure
1. Setup FastAPI application structure
2. Implement basic health check endpoint
3. Create repository interfaces và base implementation

### Phase 2: Primary Endpoints  
1. Implement /posts và /posts/{id} endpoints
2. Add pagination và basic filtering
3. Implement error handling

### Phase 3: Analytics Endpoints
1. Add /summary, /trends endpoints
2. Implement /top-keywords với JSONB aggregation
3. Add /alerts endpoint

### Phase 4: Polish
1. Complete /errors endpoint
2. Add comprehensive tests
3. Performance tuning và documentation

### Rollback Plan
- API service hoàn toàn isolated, có thể disable trong docker-compose
- Không modify existing Consumer service
- Database schemas không change

## Open Questions

1. **Rate Limiting**: Có cần implement rate limiting không? Thường API Gateway handle.
2. **Caching**: Có cần Redis cache cho frequent queries? Start simple, add later nếu cần.
3. **Async vs Sync**: All endpoints async hoặc hybrid? → All async cho consistency.
4. **Validation Level**: Frontend validation có đủ không hoặc cần strict server validation? → Implement server validation đầy đủ.