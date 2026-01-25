# Implementation Tasks

## 1. Create PVC for Model Storage

- [x] 1.1 Create `k8s/pvc-models.yaml` with PersistentVolumeClaim
  - Storage: 1Gi (PhoBERT model ~500MB)
  - AccessMode: ReadWriteOnce (hoặc ReadOnlyMany nếu multi-replica)
  - _Requirements: ai_integration_
  - **Done**: Created `k8s/pvc-models.yaml` with 1Gi storage, ReadWriteOnce access mode

## 2. Update K8s Deployment

- [x] 2.1 Add initContainer to download PhoBERT model

  - Use same Python image as main container
  - Run `scripts/download_phobert_model.py`
  - Mount model volume và MinIO credentials
  - _Requirements: ai_integration_
  - **Done**: Added `download-phobert` initContainer with cache check logic

- [x] 2.2 Change volume type from emptyDir to PVC
  - Reference PVC created in task 1.1
  - Mount at `/app/infrastructure/phobert/models`
  - _Requirements: ai_integration_
  - **Done**: Changed volume to use `smap-analytics-models` PVC

## 3. Update ConfigMap/Secret

- [x] 3.1 Ensure MinIO credentials available for initContainer
  - MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
  - Verify existing secret or add to configmap
  - _Requirements: ai_integration_
  - **Done**: MinIO credentials already exist in `smap-analytics-secret`, initContainer references them via `secretKeyRef`
