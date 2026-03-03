# Service: [TÊN SERVICE]

> **Template Version**: 1.0  
> **Last Updated**: [DATE]  
> **Status**: [🚧 In Development | ⚠️ Testing | ✅ Production Ready]

---

## 🎯 Business Context

### Chức năng chính

[Mô tả ngắn gọn service này làm gì, giải quyết vấn đề gì]

**Ví dụ**:

- Service xử lý thanh toán cho hệ thống e-commerce
- Service quản lý user authentication và authorization
- Service phân tích dữ liệu real-time từ IoT sensors

### Luồng xử lý

```
[Input]
    → [Processing Step 1]
    → [Processing Step 2]
    → [Output/Result]
```

**Ví dụ**:

```
Payment Request
    → Validate Payment Info
    → Call Payment Gateway
    → Update Order Status
    → Send Confirmation Email
```

### Giá trị cốt lõi

[Tại sao service này quan trọng? Nó mang lại giá trị gì?]

**Ví dụ**:

- Tăng conversion rate 25% nhờ checkout nhanh
- Giảm fraud rate xuống 0.5%
- Support 10+ payment methods

---

## 🛠 Technical Details

### Protocol & Architecture

- **Protocol**: [REST API | gRPC | GraphQL | WebSocket]
- **Pattern**: [Clean Architecture | MVC | Microservices | Event-Driven]
- **Design**: [Domain-Driven Design | Layered Architecture | Hexagonal]

### Tech Stack

| Component | Technology                        | Version   | Purpose            |
| --------- | --------------------------------- | --------- | ------------------ |
| Language  | [Go/Java/Python/Node.js]          | [version] | Backend service    |
| Framework | [Gin/Spring Boot/FastAPI/Express] | [version] | HTTP routing       |
| Database  | [PostgreSQL/MongoDB/MySQL]        | [version] | Primary data store |
| Cache     | [Redis/Memcached]                 | [version] | Caching layer      |
| Queue     | [Kafka/RabbitMQ/SQS]              | [version] | Async messaging    |
| Storage   | [S3/MinIO/GCS]                    | [version] | File storage       |

### Database Schema

#### [Database Type] Tables/Collections

**1. [table_name]** - [Mô tả ngắn]

```sql
CREATE TABLE [schema].[table_name] (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    [field1] VARCHAR(100) NOT NULL,
    [field2] JSONB,
    [field3] TIMESTAMPTZ DEFAULT NOW(),
    -- Add more fields
);
-- Indexes: [list important indexes]
```

**2. [table_name_2]** - [Mô tả ngắn]

```sql
-- Schema definition
```

**Lưu ý**:

- Liệt kê tất cả tables/collections quan trọng
- Highlight các relationships (FK, references)
- Note về indexes và performance considerations

---

## 📡 API Endpoints

### Domain/Module 1: [Tên Domain]

#### `[METHOD] /api/v1/[endpoint]`

**Purpose**: [Mô tả ngắn gọn endpoint làm gì]

**Authentication**: [JWT | API Key | OAuth2 | Public]

**Request**:

```json
{
  "field1": "value",
  "field2": 123,
  "nested": {
    "field3": true
  }
}
```

**Response** (Success - 200):

```json
{
  "id": "uuid",
  "status": "success",
  "data": {
    "result": "value"
  }
}
```

**Response** (Error - 400/500):

```json
{
  "error_code": 1001,
  "message": "Validation failed",
  "details": {
    "field": "field1",
    "reason": "required"
  }
}
```

**Business Logic Flow**:

1. Validate input
2. Check permissions
3. Process business logic
4. Update database
5. Return response

**Performance**:

- Avg latency: [Xms]
- Throughput: [X req/s]
- Cache: [Yes/No, TTL if applicable]

---

#### `[METHOD] /api/v1/[endpoint2]`

[Repeat structure for each endpoint]

---

### Domain/Module 2: [Tên Domain]

[Repeat endpoint documentation]

---

## 🔗 Integration & Dependencies

### External Services

**1. [Service Name]** (Upstream/Downstream)

- **Method**: [HTTP API | gRPC | Message Queue]
- **Purpose**: [Tại sao cần integrate]
- **Endpoints Used**:
  - `GET /api/resource` - [Purpose]
  - `POST /api/action` - [Purpose]
- **Error Handling**: [Retry strategy, fallback]
- **SLA**: [Response time, availability]

**2. [Service Name 2]**
[Repeat structure]

### Infrastructure Dependencies

**Message Queue** ([Kafka/RabbitMQ/etc])

```
Topic/Queue: [name]
Consumer Group: [group-id]
Message Format: {
  "event_type": "string",
  "payload": {}
}
Handler: [What happens when message received]
```

**Cache** ([Redis/etc])

```
Key Patterns:
- cache:[resource]:[id] → [data structure] (TTL: Xm)
- session:[user_id] → [session data] (TTL: Xh)

Invalidation Strategy: [When/how cache is cleared]
```

**Database** ([PostgreSQL/etc])

```
Connection Pool: [max connections]
Schema: [schema name]
Migrations: [How managed - Flyway/Liquibase/manual]
```

---

## 🎨 Key Features & Highlights

### 1. [Feature Name]

**Description**: [Chi tiết feature]

**Implementation**:

- [Technical approach]
- [Key algorithms/patterns used]
- [Performance optimizations]

**Benefits**:

- [Business value]
- [Technical advantages]

### 2. [Feature Name 2]

[Repeat structure]

### 3. Performance Optimizations

- **Caching Strategy**: [Multi-tier, write-through, etc]
- **Database Optimization**: [Indexes, query optimization]
- **Concurrency**: [How handled - goroutines, threads, async]
- **Connection Pooling**: [Settings and rationale]

### 4. Reliability Features

- **Retry Logic**: [Exponential backoff, max retries]
- **Circuit Breaker**: [When/how triggered]
- **Graceful Degradation**: [Fallback strategies]
- **Health Checks**: [Endpoints and what they check]

---

## 🚧 Status & Roadmap

### ✅ Done (Implemented & Tested)

- [x] Feature 1 - [Brief description]
- [x] Feature 2 - [Brief description]
- [x] API endpoints for [domain]
- [x] Database schema and migrations
- [x] Unit tests (coverage: X%)
- [x] Integration tests
- [x] Docker deployment

### 🔄 In Progress

- [ ] Feature X - [Status: 70% complete]
- [ ] Performance optimization - [Status: Testing]
- [ ] Documentation - [Status: Review]

### 📋 Todo (Planned)

- [ ] Feature Y - [Priority: High]
- [ ] Feature Z - [Priority: Medium]
- [ ] Monitoring dashboard - [Priority: High]
- [ ] Load testing - [Priority: Medium]

### 🐛 Known Bugs

- [ ] Bug #123: [Description] - [Severity: High/Medium/Low]
- [ ] Bug #124: [Description] - [Workaround: ...]

---

## ⚠️ Known Issues & Limitations

### 1. [Issue Category - e.g., Performance]

**Issue**: [Mô tả vấn đề cụ thể]

- **Current**: [Hiện tại đang làm như thế nào]
- **Problem**: [Vấn đề gì xảy ra]
- **Impact**: [Ảnh hưởng đến system/users]
- **Workaround**: [Giải pháp tạm thời nếu có]
- **TODO**: [Cần làm gì để fix]

**Code location**: `[path/to/file.ext]`

```[language]
// ❌ Current implementation
[code snippet showing problem]

// ✅ Proposed solution
[code snippet showing fix]
```

### 2. [Issue Category 2]

[Repeat structure]

**Common Issue Categories**:

- Performance bottlenecks
- Scalability limits
- Security concerns
- Error handling gaps
- Missing features
- Technical debt
- Configuration issues
- Monitoring gaps
- Testing coverage
- Documentation gaps

---

## 🔮 Future Enhancements

### Short-term (1-2 months)

- [ ] [Enhancement 1] - [Why important]
- [ ] [Enhancement 2] - [Why important]
- [ ] [Enhancement 3] - [Why important]

### Mid-term (3-6 months)

- [ ] [Enhancement 4] - [Why important]
- [ ] [Enhancement 5] - [Why important]

### Long-term (6+ months)

- [ ] [Enhancement 6] - [Why important]
- [ ] [Enhancement 7] - [Why important]

---

## 🔧 Configuration

**File**: `config/[service-name]-config.yaml`

```yaml
environment:
  name: [development|staging|production]

server:
  port: 8080
  mode: [debug|release]
  timeout: 30s

database:
  host: [hostname]
  port: 5432
  name: [dbname]
  pool_size: 25

cache:
  host: [hostname]
  port: 6379
  ttl: 300s

external_services:
  service_name:
    url: [base_url]
    timeout: 10s
    retry: 3

# Add all configuration sections
```

**Environment Variables**:

```bash
# Required
SERVICE_PORT=8080
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
API_KEY=xxx

# Optional
LOG_LEVEL=info
CACHE_TTL=300
```

---

## 📊 Performance Metrics

### Actual Benchmarks

[Nếu đã có load testing results]

| Metric            | Value   | Target      | Status   |
| ----------------- | ------- | ----------- | -------- |
| Avg Response Time | Xms     | <100ms      | ✅/⚠️/❌ |
| P95 Response Time | Xms     | <200ms      | ✅/⚠️/❌ |
| P99 Response Time | Xms     | <500ms      | ✅/⚠️/❌ |
| Throughput        | X req/s | >1000 req/s | ✅/⚠️/❌ |
| Error Rate        | X%      | <0.1%       | ✅/⚠️/❌ |
| CPU Usage         | X%      | <70%        | ✅/⚠️/❌ |
| Memory Usage      | XMB     | <2GB        | ✅/⚠️/❌ |

### Estimated Performance

[Nếu chưa có actual benchmarks]

**Note**: Đây là estimates dựa trên code analysis, chưa có actual load tests

- **Operation A**: ~Xms per request
- **Operation B**: ~Xs for batch of Y items
- **Cache Hit Rate**: ~X%
- **Database Query Time**: ~Xms average

**TODO**: Run load tests để có accurate numbers

---

## 🔐 Security

### Authentication

- **Method**: [JWT | OAuth2 | API Key | mTLS]
- **Token Storage**: [Cookie | Header | Session]
- **Token Expiry**: [Duration]
- **Refresh Strategy**: [How tokens are refreshed]

### Authorization

- **Model**: [RBAC | ABAC | ACL]
- **Permissions**: [List key permissions]
- **Scope Validation**: [How access is checked]

### Data Protection

- **Encryption at Rest**: [Yes/No, method]
- **Encryption in Transit**: [TLS version]
- **PII Handling**: [How sensitive data is protected]
- **Secrets Management**: [Vault | AWS Secrets Manager | Env vars]

### Security Best Practices

- [ ] Input validation and sanitization
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] CSRF protection
- [ ] Rate limiting
- [ ] API authentication
- [ ] Audit logging
- [ ] Dependency scanning
- [ ] Security headers

---

## 🧪 Testing

### Test Coverage

- **Unit Tests**: X% coverage
- **Integration Tests**: Y scenarios
- **E2E Tests**: Z critical paths
- **Load Tests**: [Completed/Planned]

### Running Tests

```bash
# Unit tests
make test

# Integration tests
make test-integration

# E2E tests
make test-e2e

# Load tests
make test-load

# Coverage report
make coverage
```

### Test Strategy

- **Unit Tests**: [What's covered]
- **Integration Tests**: [What's covered]
- **Mocking Strategy**: [How external deps are mocked]
- **Test Data**: [How test data is managed]

---

## 🚀 Deployment

### Docker

```bash
# Build
docker build -t [service-name]:latest .

# Run
docker run -d -p 8080:8080 \
  -e DATABASE_URL=... \
  -e REDIS_URL=... \
  [service-name]:latest
```

### Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: [service-name]
spec:
  replicas: 3
  selector:
    matchLabels:
      app: [service-name]
  template:
    metadata:
      labels:
        app: [service-name]
    spec:
      containers:
      - name: [service-name]
        image: [service-name]:latest
        ports:
        - containerPort: 8080
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: [service-name]-secrets
              key: database-url
```

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: make test
      - name: Build Docker image
        run: docker build -t [service-name] .
      - name: Deploy to [environment]
        run: [deployment command]
```

---

## 📚 Documentation

### API Documentation

- **Swagger/OpenAPI**: [URL to Swagger UI]
- **Postman Collection**: [Link to collection]
- **API Examples**: [Link to examples repo]

### Architecture Docs

- **System Design**: [Link to design doc]
- **Database Schema**: [Link to ERD]
- **Sequence Diagrams**: [Link to diagrams]

### Developer Guides

- **Setup Guide**: [Link to setup instructions]
- **Contributing Guide**: [Link to CONTRIBUTING.md]
- **Code Style Guide**: [Link to style guide]

---

## 📞 Contact & Support

### Team

- **Service Owner**: [Name/Team]
- **Tech Lead**: [Name]
- **On-call**: [Slack channel / PagerDuty]

### Resources

- **Repository**: [GitHub/GitLab URL]
- **Issue Tracker**: [Jira/GitHub Issues URL]
- **Monitoring**: [Grafana/Datadog dashboard URL]
- **Logs**: [Kibana/CloudWatch URL]
- **Slack Channel**: #[channel-name]

### SLA & Support

- **Availability Target**: 99.9%
- **Response Time**: [P0: 15min, P1: 1hr, P2: 4hr, P3: 1 day]
- **Support Hours**: [24/7 | Business hours]

---

## 📝 Changelog

### [Version] - [Date]

**Added**

- [New feature 1]
- [New feature 2]

**Changed**

- [Modified behavior 1]
- [Updated dependency X to version Y]

**Fixed**

- [Bug fix 1]
- [Bug fix 2]

**Deprecated**

- [Feature being phased out]

**Removed**

- [Removed feature]

**Security**

- [Security patch]

---

## 🎓 Learning Resources

### Internal Docs

- [Link to internal wiki]
- [Link to architecture decision records]
- [Link to runbooks]

### External Resources

- [Official documentation of key technologies]
- [Relevant blog posts]
- [Video tutorials]

---

## 📋 Appendix

### Glossary

- **Term 1**: Definition
- **Term 2**: Definition
- **Acronym**: Full form and meaning

### Related Services

- **[Service A]**: [How it relates]
- **[Service B]**: [How it relates]

### Migration Guides

- [Link to migration guide from v1 to v2]
- [Link to breaking changes document]

---

**Document Version**: 1.0  
**Last Updated**: [DATE]  
**Maintained By**: [Team/Person]  
**Review Cycle**: [Monthly/Quarterly]

---

## 📌 Quick Reference Card

```
Service: [NAME]
Port: [PORT]
Health: GET /health
Metrics: GET /metrics
Swagger: [URL]

Quick Start:
1. Clone repo
2. Copy config: cp config.example.yaml config.yaml
3. Run: make run
4. Test: curl http://localhost:[PORT]/health

Common Commands:
- Start: make run
- Test: make test
- Build: make build
- Deploy: make deploy

Emergency Contacts:
- On-call: [Slack/Phone]
- Escalation: [Manager/Team Lead]
```
