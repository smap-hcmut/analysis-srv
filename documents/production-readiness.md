# Production Readiness Guide — analysis-srv

> Ngày đánh giá: 09/04/2026  
> Trạng thái tổng thể: **CHƯA SẴN SÀNG CHO PRODUCTION** — có 2 lỗi critical cần fix trước khi deploy.

---

## Mục lục

1. [Đánh giá tổng quan](#1-đánh-giá-tổng-quan)
2. [Vấn đề Critical (phải fix trước khi deploy)](#2-vấn-đề-critical)
3. [Vấn đề High (fix trong sprint đầu tiên)](#3-vấn-đề-high)
4. [Vấn đề Medium (fix trong 1-2 sprint)](#4-vấn-đề-medium)
5. [Vấn đề Low (tech debt)](#5-vấn-đề-low)
6. [Hướng dẫn deploy từng bước](#6-hướng-dẫn-deploy-từng-bước)
7. [Scaling và tối ưu hiệu năng](#7-scaling-và-tối-ưu-hiệu-năng)
8. [Checklist trước khi go-live](#8-checklist-trước-khi-go-live)

---

## 1. Đánh giá tổng quan

### Điều service làm tốt

- **Pipeline architecture rõ ràng**: 9 stage có thể bật/tắt độc lập qua config flag.
- **Asyncio đúng chỗ**: CPU-bound pipeline chạy qua `asyncio.to_thread()`, không block event loop.
- **Graceful shutdown**: signal handler → `server.shutdown()` → `consumer.stop()` đã có.
- **Config externalized**: tất cả config đọc từ `config/config.yaml`, mount qua ConfigMap.
- **Test coverage tốt**: 180 unit tests pass, cover hầu hết domain logic.
- **Structured logging**: loguru với JSON output, sẵn sàng cho log aggregator (Loki, ELK).

### Điều service chưa làm được

| Mức độ | Số lượng vấn đề |
|--------|----------------|
| Critical | 2 |
| High | 3 |
| Medium | 4 |
| Low | 4 |

---

## 2. Vấn đề Critical

### C1 — Kafka offset không bao giờ được commit

**File:** `pkg/kafka/consumer.py:76-127`, `apps/consumer/main.py:166`

**Vấn đề:**  
Consumer được cấu hình `enable_auto_commit=False` (đúng — để đảm bảo at-least-once), nhưng `consumer.commit()` **không bao giờ được gọi** sau khi xử lý message thành công. Hậu quả: mỗi lần pod restart, toàn bộ message từ đầu partition sẽ bị reprocess. Trong production với volume cao, điều này gây duplicate processing và có thể làm tràn database.

**Fix:**  
Trong `pkg/kafka/consumer.py`, gọi `commit()` sau khi `message_handler` hoàn thành thành công:

```python
# pkg/kafka/consumer.py — trong vòng lặp consume()
async for msg in self.consumer:
    try:
        kafka_msg = KafkaMessage(...)
        await message_handler(kafka_msg)
        await self.consumer.commit()          # <-- THÊM DÒNG NÀY
    except Exception as e:
        logger.error(...)
        # Không commit khi lỗi — message sẽ được retry khi restart
```

**Lưu ý:** Chỉ commit sau khi handler thành công. Nếu handler raise exception, không commit để đảm bảo message được xử lý lại.

---

### C2 — Credentials thật commit lên Git

**Files:**  

- `manifests/configmap.yaml:9-36` — chứa database URL với password, Redis password, MinIO credentials  
- `manifests/secret.yaml:12-20` — chứa passwords dạng plaintext

**Vấn đề:**  
Passwords thật (`analysis_prod_pwd`, `21042004`) đang nằm trong Git repository. Bất kỳ ai có quyền đọc repo đều thấy credentials production.

**Fix ngắn hạn:** Thay bằng placeholder và dùng `secretKeyRef` trong Deployment:

```yaml
# manifests/secret.yaml — thay passwords bằng placeholder
stringData:
  DB_PASSWORD: "<CHANGE_ME>"
  REDIS_PASSWORD: "<CHANGE_ME>"
  MINIO_SECRET_KEY: "<CHANGE_ME>"
```

```yaml
# apps/consumer/deployment.yaml — mount secret vào env
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: analysis-secrets
        key: DB_PASSWORD
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: analysis-secrets
        key: REDIS_PASSWORD
```

```yaml
# manifests/configmap.yaml — dùng env var thay vì hardcode
database:
  url: "postgresql+asyncpg://analysis_prod:$(DB_PASSWORD)@172.16.19.10:5432/smap"
```

**Fix dài hạn:** Dùng Kubernetes Sealed Secrets hoặc Vault Agent Injector. Credentials chỉ tồn tại trong Vault/Sealed Secret, không bao giờ ở plaintext trong Git.

**Quan trọng:** Nếu repo đã public hoặc đã share, cần **rotate tất cả passwords ngay lập tức** ngay cả sau khi đã xóa khỏi Git (Git history vẫn còn).

---

## 3. Vấn đề High

### H1 — Prometheus metrics HTTP server không bao giờ start

**Vấn đề:**  
Metrics có thể được định nghĩa trong code nhưng endpoint `/metrics` chưa được expose. Kubernetes (hay Prometheus Operator) không thể scrape metrics từ pod.

**Fix:** Thêm metrics HTTP server vào `apps/consumer/main.py`:

```python
# Thêm vào init_dependencies() hoặc main()
from prometheus_client import start_http_server
start_http_server(port=9090, addr="0.0.0.0")
logger.info("Prometheus metrics server started on :9090")
```

```yaml
# apps/consumer/deployment.yaml — expose port
ports:
  - name: metrics
    containerPort: 9090
    protocol: TCP
```

```yaml
# Thêm ServiceMonitor hoặc Annotations cho Prometheus scraping
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "9090"
  prometheus.io/path: "/metrics"
```

---

### H2 — Không có liveness/readiness probes

**File:** `apps/consumer/deployment.yaml`

**Vấn đề:**  
Kubernetes không biết khi nào pod bị deadlock hoặc chưa sẵn sàng nhận traffic. Pod có thể bị stuck mà không bị restart.

**Fix:** Thêm HTTP health endpoint và probe:

```python
# Thêm health server song song với consumer loop trong main.py
from aiohttp import web

async def health_app(is_ready: asyncio.Event):
    app = web.Application()

    async def liveness(_):
        return web.Response(text="ok")

    async def readiness(_):
        if is_ready.is_set():
            return web.Response(text="ready")
        return web.Response(status=503, text="not ready")

    app.router.add_get("/healthz", liveness)
    app.router.add_get("/readyz", readiness)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    return runner
```

```yaml
# apps/consumer/deployment.yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 15
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /readyz
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 2
```

---

### H3 — Message thất bại bị drop âm thầm, không có DLQ

**File:** `pkg/kafka/consumer.py:116-121`

**Vấn đề:**  
Khi `message_handler` raise exception, lỗi chỉ được log rồi bỏ qua. Message không được retry, không có dead letter queue. Dữ liệu quan trọng mất mà không biết.

**Fix tối thiểu (DLQ topic):**

```python
# pkg/kafka/consumer.py
async for msg in self.consumer:
    try:
        await message_handler(kafka_msg)
        await self.consumer.commit()
    except Exception as e:
        logger.error(f"Processing failed, sending to DLQ: {e}")
        await self._send_to_dlq(msg)   # publish sang topic smap.analytics.dlq
        await self.consumer.commit()   # commit để không stuck
```

Tạo topic `smap.analytics.dlq` trong Kafka và có consumer riêng để xử lý lại hoặc alert.

---

## 4. Vấn đề Medium

### M1 — Outbox relay loop là dead code

**File:** `scripts/relay_outbox.py` (hoặc tương đương trong internal/)

**Vấn đề:**  
Bảng `analytics_outbox` được tạo trong migration (`001_create_analytics_outbox.sql`) và được write bởi pipeline, nhưng relay loop (đọc outbox → publish ra Kafka) chưa được wire vào consumer startup.

**Fix:** Khởi chạy relay loop như background `asyncio.Task` trong `ConsumerServer.start()`:

```python
# internal/consumer/server.py — trong start()
self.outbox_task = asyncio.create_task(
    self._run_outbox_relay(), name="outbox-relay"
)

async def _run_outbox_relay(self):
    while self._running:
        try:
            await self.registry.outbox_relay.relay_once()
        except Exception as e:
            self.logger.error(f"Outbox relay error: {e}")
        await asyncio.sleep(5)  # poll interval
```

---

### M2 — Secrets định nghĩa trong secret.yaml nhưng Deployment không mount

**File:** `apps/consumer/deployment.yaml:41-66`

**Vấn đề:**  
`secret.yaml` tạo Secret `analysis-secrets` với DB_PASSWORD, REDIS_PASSWORD, MINIO_SECRET_KEY, nhưng Deployment không có `secretKeyRef` nào. Config đọc passwords trực tiếp từ ConfigMap (plaintext).

**Fix:** Xem phần C2 ở trên — wire `secretKeyRef` vào Deployment env và dùng `$(ENV_VAR)` interpolation trong ConfigMap value.

---

### M3 — Không có migration framework, chỉ có raw SQL

**Files:** `migration/init_db.sql`, `migration/001_*.sql`, `migration/002_*.sql`

**Vấn đề:**  
SQL files không có version tracking. Không biết database hiện tại đang ở schema version nào. Chạy lại `init_db.sql` trên production database sẽ drop tables.

**Fix:** Dùng **Alembic** (Python-native, tích hợp tốt với SQLAlchemy):

```bash
uv add alembic
alembic init alembic
```

Convert các SQL file hiện tại thành Alembic migration files. Thêm bước `alembic upgrade head` vào CI/CD pipeline trước khi deploy pod mới.

---

### M4 — Không có HPA, replicas cố định là 1

**File:** `apps/consumer/deployment.yaml:11`

**Vấn đề:**  
`replicas: 1` — một pod chết là service down. Không scale được khi Kafka consumer lag tăng.

**Fix:** Tạo HPA dựa trên Kafka consumer lag (dùng KEDA):

```yaml
# manifests/keda-scaledobject.yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: analysis-consumer-scaler
  namespace: smap
spec:
  scaleTargetRef:
    name: analysis-consumer
  minReplicaCount: 2        # tối thiểu 2 cho HA
  maxReplicaCount: 10
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092
        consumerGroup: analytics-service
        topic: smap.collector.output
        lagThreshold: "100"   # scale up khi lag > 100 messages/replica
```

**Lưu ý Kafka consumer group + partitions:** Số replicas tối đa có ý nghĩa = số partitions của topic. Nếu topic có 6 partitions, tối đa 6 consumer instances. Cần tăng partitions nếu muốn scale > 6.

---

## 5. Vấn đề Low

### L1 — `PYTHONWARNINGS=ignore::SyntaxWarning` che giấu lỗi thật

**File:** `apps/consumer/deployment.yaml:46-47`

Xóa env var này. Nếu có SyntaxWarning từ dependency, fix dependency hoặc pin version cụ thể thay vì im lặng.

---

### L2 — `aio-pika` là phantom dependency

Nếu không dùng RabbitMQ, xóa `aio-pika` khỏi `pyproject.toml` để giảm image size và attack surface.

---

### L3 — Không có distributed tracing

Service chưa có OpenTelemetry. Không thể trace request qua nhiều service.

**Fix nhanh:**

```bash
uv add opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-asyncio
```

Thêm trace span quanh `_handle_message()` với `run_id` làm trace attribute.

---

### L4 — Thiếu integration tests và load tests

Unit tests cover tốt (180/180) nhưng không có:

- Integration test với real Kafka + PostgreSQL (dùng `testcontainers-python`)
- Load test để biết throughput thực tế (messages/giây) trước khi lên production

---

## 6. Hướng dẫn deploy từng bước

### Bước 0: Prerequisites

```bash
# Cài đặt tools
kubectl version  # >= 1.28
helm version     # >= 3.12
uv --version     # >= 0.4
```

### Bước 1: Fix Critical issues trước

Phải hoàn thành C1 (Kafka commit) và C2 (credentials) trước khi tiếp tục.

### Bước 2: Build và push image

```bash
# Build base image (có PhoB ERT model)
./scripts/build-base.sh

# Build consumer image
./scripts/build-consumer.sh

# Verify image
docker run --rm registry.tantai.dev/smap/analysis-consumer:<tag> python -c "import internal.consumer"
```

### Bước 3: Chạy database migration

```bash
# Tạo namespace nếu chưa có
kubectl create namespace smap

# Chạy migration (cần kết nối tới DB từ trong cluster)
kubectl run migration-job \
  --image=registry.tantai.dev/smap/analysis-consumer:<tag> \
  --restart=Never \
  --namespace=smap \
  -- python scripts/run_migration.py

kubectl wait --for=condition=complete job/migration-job -n smap --timeout=60s
kubectl logs migration-job -n smap
kubectl delete pod migration-job -n smap
```

### Bước 4: Apply manifests

```bash
# Apply theo đúng thứ tự
kubectl apply -f manifests/secret.yaml        # 1. secrets trước
kubectl apply -f manifests/configmap.yaml     # 2. configmap
kubectl apply -f apps/consumer/deployment.yaml # 3. deployment

# Verify
kubectl rollout status deployment/analysis-consumer -n smap
kubectl get pods -n smap -l app=analysis-consumer
```

### Bước 5: Verify health

```bash
# Check logs
kubectl logs -f deployment/analysis-consumer -n smap

# Expect log lines như:
# INFO  PostgreSQL connection verified
# INFO  Redis connection verified
# INFO  Kafka consumer started, waiting for messages...
```

### Bước 6: Verify Kafka consumption

```bash
# Kiểm tra consumer group lag
kubectl exec -n kafka kafka-cluster-kafka-0 -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group analytics-service
```

Cột `LAG` phải giảm dần (consumer đang xử lý), không tăng liên tục.

---

## 7. Scaling và tối ưu hiệu năng

### Throughput hiện tại (ước tính)

| Component | Bottleneck | Ước tính |
|-----------|------------|----------|
| Kafka consume | aiokafka async | ~1000 msg/s |
| NLP pipeline (PhoB ERT) | ONNX inference, CPU-bound | ~5-20 msg/s per thread |
| PostgreSQL write | connection pool size 20 | ~200 writes/s |
| End-to-end | NLP là bottleneck | **~5-20 msg/s per pod** |

### Tối ưu NLP throughput

**Option 1: Batch inference** — thay vì xử lý từng message, gom thành batch 8-16 messages rồi inference 1 lần với PhoB ERT. Cải thiện ~3-5x throughput do ONNX optimize batch operations.

```python
# internal/consumer/server.py — thay vì xử lý từng message:
# Gom message vào buffer, flush khi đủ batch_size hoặc timeout
self._message_buffer: list[KafkaMessage] = []
self._batch_size = 16
self._batch_timeout = 0.5  # seconds
```

**Option 2: Tăng worker threads** — `asyncio.to_thread()` dùng `ThreadPoolExecutor` mặc định (min(32, cpu_count+4) threads). Với NLP workload, có thể tăng lên:

```python
import concurrent.futures
loop = asyncio.get_event_loop()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
loop.set_default_executor(executor)
```

**Option 3: ONNX GPU inference** — nếu cluster có GPU node, dùng ONNX Runtime với CUDA provider. Cải thiện ~10-20x inference speed.

### Scale ngang (Horizontal Scaling)

Điều kiện để scale consumer group:

1. Kafka topic `smap.collector.output` phải có **ít nhất N partitions** để chạy N consumer instances.
2. Mỗi consumer instance là **stateless** — không share state qua memory, chỉ qua DB/Redis.
3. Dedup và spam stages dùng **distributed state qua Redis** — đã sẵn sàng.

```bash
# Tăng partitions (one-time, không thể giảm)
kubectl exec -n kafka kafka-cluster-kafka-0 -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --alter \
  --topic smap.collector.output \
  --partitions 6   # tăng từ hiện tại lên 6
```

Sau đó KEDA sẽ tự động scale deployment lên tối đa 6 replicas khi lag tăng.

### Resource tuning

```yaml
# apps/consumer/deployment.yaml — điều chỉnh sau khi benchmark
resources:
  requests:
    memory: "1Gi"    # baseline cho PhoB ERT model load
    cpu: "500m"      # baseline
  limits:
    memory: "3Gi"    # cho spike khi xử lý thread pool
    cpu: "2000m"     # tăng nếu dùng batch inference
```

**Quy tắc ngón tay cái:** CPU limit nên ≥ 2x số threads NLP worker. Memory limit nên ≥ model size (PhoB ERT ONNX ~500MB) + 1GB overhead.

---

## 8. Checklist trước khi go-live

### Must-have (Blocking)

- [ ] **C1**: Kafka `commit()` được gọi sau mỗi message thành công
- [ ] **C2**: Credentials được xóa khỏi Git, rotate passwords, dùng `secretKeyRef`
- [ ] **H2**: Liveness + readiness probes đã có trong Deployment
- [ ] **M3**: Database migration chạy thành công trên production DB
- [ ] Image được build từ locked dependencies (`uv.lock`) không phải `latest`

### Should-have (First sprint)

- [ ] **H1**: Prometheus metrics endpoint expose trên `:9090`
- [ ] **H3**: Dead letter queue topic `smap.analytics.dlq` được tạo và monitored
- [ ] **M1**: Outbox relay loop được wire vào startup
- [ ] **M4**: HPA với KEDA, minimum 2 replicas
- [ ] Kafka topic có ít nhất 2 partitions cho HA

### Nice-to-have (Next sprints)

- [ ] **M3**: Migrate từ raw SQL sang Alembic
- [ ] **L3**: OpenTelemetry tracing
- [ ] **L1**: Xóa `PYTHONWARNINGS=ignore::SyntaxWarning`
- [ ] Integration tests với testcontainers
- [ ] Runbook / Playbook cho các alert scenario phổ biến

---

## Tóm tắt nhanh

```
Service CÓ THỂ chạy được nhưng:

1. Mỗi lần pod restart → reprocess toàn bộ Kafka messages từ đầu   [FIX NGAY]
2. Passwords thật trong Git repository                              [FIX NGAY]
3. Kubernetes không detect pod bị stuck (không có health probes)    [FIX TRƯỚC DEPLOY]
4. Kafka lag không có autoscaling                                   [FIX TRONG 1 SPRINT]

Sau khi fix 4 điểm trên, service có thể chạy production ở scale nhỏ.
Để scale lớn hơn: batch NLP inference + tăng Kafka partitions + KEDA HPA.
```
