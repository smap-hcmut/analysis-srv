## ADDED Requirements

### Requirement: API Service Foundation

The system SHALL provide a RESTful API service built with FastAPI to serve analytics data to dashboard clients.

#### Scenario: API service startup
- **WHEN** API service is started via command/api/main.py
- **THEN** FastAPI application starts on configured host:port
- **AND** all routes are registered and accessible
- **AND** Swagger UI documentation is available at /swagger/index.html

#### Scenario: Health check endpoint
- **WHEN** GET /health request is made
- **THEN** response returns {"status": "healthy"} with 200 status
- **AND** response time is under 10ms

### Requirement: Posts Listing API

The system SHALL provide GET /api/v1/analytics/posts endpoint to retrieve paginated list of analyzed posts with comprehensive filtering.

#### Scenario: Basic posts retrieval
- **WHEN** GET /api/v1/analytics/posts?project_id=uuid request is made
- **THEN** response includes success=true, data array, pagination metadata
- **AND** each post includes id, platform, permalink, content_text (truncated), author info, sentiment, impact metrics
- **AND** pagination includes page, page_size, total_items, total_pages, has_next, has_prev

#### Scenario: Posts filtering by brand and keyword
- **WHEN** GET /api/v1/analytics/posts?project_id=uuid&brand_name=Samsung&keyword=Galaxy request is made
- **THEN** only posts matching all filter criteria are returned
- **AND** filtering is case-insensitive for string fields

#### Scenario: Posts sorting and pagination
- **WHEN** GET /api/v1/analytics/posts?project_id=uuid&sort_by=impact_score&sort_order=desc&page=2&page_size=20 request is made
- **THEN** posts are sorted by impact_score descending
- **AND** returns items 21-40 based on page=2, page_size=20
- **AND** pagination metadata reflects correct page position

### Requirement: Post Detail API

The system SHALL provide GET /api/v1/analytics/posts/{post_id} endpoint to retrieve complete post analysis including aspects breakdown and comments.

#### Scenario: Successful post detail retrieval
- **WHEN** GET /api/v1/analytics/posts/tiktok_7441234567890 request is made
- **THEN** response includes full post content, complete author info, sentiment probabilities
- **AND** includes aspects_breakdown with DESIGN/PERFORMANCE/PRICE/SERVICE/GENERAL aspects
- **AND** includes keywords array with aspect mapping and sentiment scores
- **AND** includes impact_breakdown with engagement_score, reach_score calculations

#### Scenario: Post not found
- **WHEN** GET /api/v1/analytics/posts/nonexistent_id request is made
- **THEN** response returns 404 status with success=false
- **AND** error object includes code="RES_001", message about post not found

### Requirement: Analytics Summary API

The system SHALL provide GET /api/v1/analytics/summary endpoint to retrieve aggregated statistics for dashboard overview.

#### Scenario: Summary data aggregation
- **WHEN** GET /api/v1/analytics/summary?project_id=uuid&from_date=2025-12-01&to_date=2025-12-19 request is made
- **THEN** response includes total_posts, total_comments counts
- **AND** includes sentiment_distribution with POSITIVE/NEUTRAL/NEGATIVE counts
- **AND** includes risk_distribution with CRITICAL/HIGH/MEDIUM/LOW counts
- **AND** includes platform_distribution and engagement_totals

### Requirement: Trends Timeline API

The system SHALL provide GET /api/v1/analytics/trends endpoint to retrieve time-series data for dashboard charts.

#### Scenario: Daily trends aggregation
- **WHEN** GET /api/v1/analytics/trends?project_id=uuid&granularity=day&from_date=2025-12-15&to_date=2025-12-17 request is made
- **THEN** response includes items array with daily aggregations
- **AND** each item includes date, post_count, avg_sentiment_score, sentiment_breakdown
- **AND** granularity options support "day", "week", "month"

### Requirement: Top Keywords API

The system SHALL provide GET /api/v1/analytics/top-keywords endpoint to retrieve most frequent keywords with sentiment analysis.

#### Scenario: Keywords aggregation with sentiment
- **WHEN** GET /api/v1/analytics/top-keywords?project_id=uuid&limit=20 request is made
- **THEN** response includes keywords array sorted by count descending
- **AND** each keyword includes count, avg_sentiment_score, aspect, sentiment_breakdown
- **AND** limit parameter constrains result size (max 50)

### Requirement: Alerts API

The system SHALL provide GET /api/v1/analytics/alerts endpoint to retrieve posts requiring attention based on risk level and viral status.

#### Scenario: Critical alerts identification
- **WHEN** GET /api/v1/analytics/alerts?project_id=uuid request is made
- **THEN** response includes critical_posts array with CRITICAL risk level posts
- **AND** includes viral_posts array with is_viral=true posts
- **AND** includes crisis_intents array with primary_intent=CRISIS posts
- **AND** includes summary counts for each alert type

### Requirement: Crawl Errors API

The system SHALL provide GET /api/v1/analytics/errors endpoint to retrieve crawler error logs with pagination.

#### Scenario: Error logs retrieval
- **WHEN** GET /api/v1/analytics/errors?project_id=uuid request is made
- **THEN** response includes paginated error records from crawl_errors table
- **AND** each error includes content_id, platform, error_code, error_category, error_message
- **AND** supports filtering by job_id, error_code, date range

### Requirement: Request Validation

The system SHALL validate all incoming API requests and return structured error responses for validation failures.

#### Scenario: Missing required parameter
- **WHEN** GET /api/v1/analytics/posts request is made without project_id parameter
- **THEN** response returns 400 status with success=false
- **AND** error object includes code="VAL_003", message about required field missing
- **AND** details array specifies which field is missing

#### Scenario: Invalid parameter format
- **WHEN** GET /api/v1/analytics/posts?project_id=invalid-uuid request is made
- **THEN** response returns 400 status with success=false
- **AND** error object includes code="VAL_002", message about invalid format

### Requirement: Response Format Standardization

The system SHALL return all API responses in standardized format with consistent metadata.

#### Scenario: Success response structure
- **WHEN** any successful API request is made
- **THEN** response includes success=true, data object/array
- **AND** meta object includes timestamp, request_id, version
- **AND** request_id is unique UUID for request tracing

#### Scenario: Paginated response structure
- **WHEN** paginated endpoint returns results
- **THEN** response includes pagination object with page, page_size, total_items, total_pages
- **AND** includes has_next, has_prev boolean flags for navigation

#### Scenario: Error response structure
- **WHEN** any error occurs during request processing
- **THEN** response includes success=false, error object
- **AND** error object includes code, message, details array
- **AND** meta object includes timestamp, request_id for debugging

### Requirement: Database Performance

The system SHALL optimize database queries for API response times under 100ms for typical list operations.

#### Scenario: Query optimization with indexes
- **WHEN** database queries are executed for API endpoints
- **THEN** composite indexes exist for common filter combinations (project_id + brand_name + keyword)
- **AND** date range queries use dedicated indexes on published_at/analyzed_at columns
- **AND** pagination queries use offset-based approach with limits

#### Scenario: Large dataset handling
- **WHEN** API requests involve large result sets
- **THEN** pagination is enforced with max page_size of 100 items
- **AND** database queries use LIMIT/OFFSET for memory efficiency
- **AND** JSONB aggregations are optimized for keywords endpoint

### Requirement: Deployment Configuration

The system SHALL provide comprehensive deployment configurations for both development and production environments.

#### Scenario: Environment variable management
- **WHEN** API service is deployed to different environments
- **THEN** .env.example includes all required API service variables
- **AND** environment validation occurs at startup
- **AND** API-specific configuration is isolated in dedicated section

#### Scenario: Kubernetes deployment
- **WHEN** API service is deployed to Kubernetes cluster
- **THEN** deployment.yaml configures pods with proper resource limits and health checks
- **AND** service.yaml provides load balancing across pod replicas
- **AND** ingress.yaml enables external access with proper routing
- **AND** horizontal pod autoscaler scales based on CPU/memory usage

#### Scenario: Production readiness
- **WHEN** API service runs in production environment
- **THEN** database connection pooling is configured for concurrent requests
- **AND** structured logging captures request traces and performance metrics
- **AND** health check endpoints support Kubernetes liveness and readiness probes