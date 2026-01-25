# Change: Add K8s InitContainer for PhoBERT Model Loading

## Why

Hiện tại PhoBERT model không được load trong K8s deployment vì:

1. **emptyDir volume**: Deployment mount `emptyDir: {}` vào `/app/infrastructure/phobert/models` → folder trống mỗi lần pod start
2. **Dockerfile không download model**: Build stage không chạy `scripts/download_phobert_model.py`
3. **Kết quả**: SentimentAnalyzer bị disabled, tất cả posts trả về NEUTRAL sentiment

Log evidence:

```
WARNING | PhoBERT model not available. SentimentAnalyzer will be disabled.
All posts will receive neutral sentiment scores.
```

## What Changes

### K8s Deployment Changes

- **ADDED**: InitContainer để download PhoBERT model từ MinIO trước khi main container start
- **MODIFIED**: Volume từ `emptyDir` sang `PersistentVolumeClaim` để cache model (tránh download lại mỗi lần pod restart)
- **ADDED**: PVC manifest cho model storage

### ConfigMap Changes

- **ADDED**: MinIO credentials reference cho initContainer (MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY)

## Impact

- Affected specs: `ai_integration`
- Affected code:
  - `k8s/deployment.yaml` - Add initContainer, change volume type
  - `k8s/pvc-models.yaml` - New PVC for model storage
  - `k8s/configmap.yaml` - Add MinIO config (nếu chưa có)

## Trade-offs

### Lợi ích

- Model được load đúng cách → SentimentAnalyzer hoạt động
- PVC cache → không download lại mỗi lần pod restart
- Credentials không bake vào Docker image (bảo mật)
- Có thể update model version mà không cần rebuild image

### Hạn chế

- First pod start chậm hơn (~30s để download ~500MB model)
- Cần PVC storage class hỗ trợ ReadWriteOnce hoặc ReadOnlyMany
- Phụ thuộc MinIO availability lúc first start
