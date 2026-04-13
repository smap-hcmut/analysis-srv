# Analysis Service — Hướng dẫn vận hành

## Trạng thái hiện tại

Toàn bộ quá trình tích hợp từ core-analysis vào analysis-srv đã **hoàn tất**. Service hiện có:

| Giai đoạn | Trạng thái | Mô tả |
|-----------|-----------|-------|
| Ontology Models | Xong | Pydantic models khớp với core (`OntologyRegistry`, `EntitySeed`, `CategoryDefinition`, `TopicDefinition`, v.v.) có `model_validator` kiểm tra tham chiếu chéo |
| Kiến trúc Domain | Xong | Ontology domain tự chứa (1 file YAML mỗi domain, chứa đầy đủ entities, taxonomy, aspects, issues, intents, topics, channels) |
| Dữ liệu VinFast | Xong | `config/ontology/vinfast_vn.yaml` — 15 entities, 18 aspects, 15 issues, 10 intents, 10 topics, 28 taxonomy nodes, 6 channels |
| Tích hợp Config | Xong | `EnrichmentConfig`, `OntologyConfig.domain_ontology_path`, `PipelineStagesConfig.enable_enrichment = True` |
| Enrichment Pipeline | Xong | Entity enricher (khớp alias từ ontology), Semantic enricher (seed phrases cho aspect/issue), Topic enricher (topic seeds từ ontology + TF-IDF dự phòng) |
| Nối dây Pipeline | Xong | `ConsumerRegistry` khởi tạo `EnrichmentUseCase` với ontology, truyền vào `PipelineServices` |
| K3s Deployment | Xong | Deployment (probes, resource limits), HPA (autoscaling theo CPU), ConfigMap (thêm mục enrichment + ontology) |

### So sánh trước và sau

| Trước | Sau |
|-------|-----|
| Ontology chia 3 file (entities.yaml, taxonomy.yaml, source_channels.yaml) | 1 file YAML tự chứa cho mỗi domain |
| Entity model: dataclass đơn giản, 8 fields | `EntitySeed` Pydantic model, 17+ fields với aliases, taxonomy, neighboring refs |
| Không có aspects/issues/intents/topics trong ontology | Có đầy đủ `CategoryDefinition` và `TopicDefinition` với seed phrases |
| Enrichment stage bị tắt | Enrichment bật: entity + semantic + topic |
| Khớp entity: chỉ regex | Alias map từ ontology + regex dự phòng |
| Phát hiện aspect/issue: patterns viết cứng | Seed phrases lấy từ ontology |
| Phân loại topic: chỉ TF-IDF | Topic seeds từ ontology + TF-IDF dự phòng |

---

## Cấu trúc dự án

```
analysis-srv/
├── apps/consumer/
│   ├── main.py                     # Điểm khởi chạy
│   ├── Dockerfile                  # Image ứng dụng (FROM analysis-base)
│   └── deployment.yaml             # K3s Deployment manifest
├── config/
│   ├── config.py                   # Tất cả config dataclasses + ConfigLoader
│   ├── config.yaml                 # Config dev local (gitignored khi production)
│   ├── config.example.yaml         # Template
│   ├── ontology/
│   │   └── vinfast_vn.yaml         # Ontology domain VinFast (tự chứa)
│   └── domains/
│       ├── vinfast.yaml            # Con trỏ domain VinFast + runtime config
│       └── _default.yaml           # Domain mặc định (fallback)
├── internal/
│   ├── ontology/
│   │   ├── type.py                 # Pydantic models (OntologyRegistry, EntitySeed, v.v.)
│   │   └── usecase/
│   │       └── file_registry.py    # Load ontology YAML, cung cấp alias_map, seed phrases
│   ├── enrichment/
│   │   ├── type.py                 # 15 fact type models (EntityResolutionFact, v.v.)
│   │   └── usecase/
│   │       ├── usecase.py          # EnrichmentUseCase (điều phối)
│   │       ├── enrich_batch.py     # Logic làm giàu theo batch
│   │       ├── build_enricher_service.py  # Nối dây các sub-enrichers
│   │       ├── entity_enricher.py  # Khớp alias từ ontology + regex
│   │       ├── semantic_enricher.py # Khớp seed phrases cho aspect/issue
│   │       └── topic_enricher.py   # Khớp topic seeds + TF-IDF
│   ├── consumer/
│   │   ├── server.py               # Kafka consumer server
│   │   └── registry.py             # Khởi tạo tất cả services, nối ontology
│   ├── domain/
│   │   ├── type.py                 # DomainRuntimeConfig
│   │   └── loader.py               # Domain YAML loader
│   └── pipeline/
│       └── usecase/run_pipeline.py # Điều phối pipeline (9 stages)
├── manifests/
│   ├── configmap.yaml              # ConfigMap production
│   ├── configmap.yaml.example      # Template ConfigMap
│   ├── secret.yaml                 # Secrets production
│   ├── secret.yaml.example         # Template secrets
│   └── hpa.yaml                    # HorizontalPodAutoscaler
├── scripts/
│   ├── Dockerfile.base             # Base image (torch + PhoBERT ~2GB)
│   ├── build-base.sh               # Build & push base image
│   └── build-consumer.sh           # Build & push consumer image
└── pyproject.toml                  # Python deps (uv/hatch)
```

---

## Cách thêm domain mới

### Bước 1: Tạo file ontology YAML cho domain

Tạo `config/ontology/<domain_id>.yaml`. Đây là file **tự chứa** — mọi thứ hệ thống cần cho domain đó nằm hết trong file này. Dùng file VinFast làm template:

```bash
cp config/ontology/vinfast_vn.yaml config/ontology/beer_vn.yaml
```

Sửa file. Các mục bắt buộc:

```yaml
# === Bắt buộc ===
metadata:
  name: smap-beer-vn           # Tên duy nhất
  version: "2026.04.13"
  description: "Ontology domain bia & đồ uống cho social listening Việt Nam."

domain_id: beer_vn              # Phải duy nhất giữa tất cả domains

# Tín hiệu kích hoạt domain — hệ thống dùng để nhận diện domain nào áp dụng
activation:
  primary_min_score: 3.0
  primary_min_matched_records: 2
  signals:
    - phrase: bia
      weight: 3.0
    - phrase: heineken
      weight: 2.5
    # ... thêm tín hiệu

# Các loại entity dùng trong domain (chỉ liệt kê ID)
entity_types:
  - brand
  - product
  - category
  - feature
  # ... (bắt buộc phải có ít nhất các loại CHUNG: brand, product, person,
  #      organization, location, facility, retailer, concept)

# Cây taxonomy (categories + features)
taxonomy_nodes:
  - id: category.beer
    label: Bia
    node_type: category
  - id: feature.taste
    label: Hương vị
    node_type: feature
  # ...

# Danh mục khía cạnh (aspect) — người dùng nói về khía cạnh nào
aspect_categories:
  - id: taste
    label: Hương vị
    description: Vị, chất lượng hương vị, và trải nghiệm uống.
    seed_phrases: [vị, taste, flavor, ngon, dở, ...]
    negative_phrases: []
    compatible_entity_types: [brand, product]
    linked_topic_keys: [product_experience]
    related_issue_ids: [quality_problem]
  # ...

# Danh mục vấn đề (issue) — người dùng phàn nàn về gì
issue_categories:
  - id: quality_problem
    label: Vấn đề chất lượng
    seed_phrases: [lỗi, defect, hỏng, ...]
    compatible_entity_types: [brand, product]
    linked_topic_keys: [product_experience]
    related_aspect_ids: [taste, quality]
  # ...

# Danh mục ý định (intent) — người dùng đăng bài với mục đích gì
intent_categories:
  - id: question
    label: Câu hỏi
    seed_phrases: [hỏi, "?", bao nhiêu, ...]
  - id: complaint
    label: Phàn nàn
    seed_phrases: [thất vọng, tệ, kém, ...]
  # ... (bắt buộc phải có các intent CHUNG: question, complaint, commentary,
  #      praise, purchase_intent, compare)

# Kênh nguồn
source_channels:
  - id: tiktok
    label: TikTok
  - id: facebook
    label: Facebook
  # ...

# Entities — danh mục thương hiệu, sản phẩm, người, v.v.
entities:
  - id: heineken
    name: Heineken
    entity_type: brand
    entity_kind: entity
    knowledge_layer: domain      # "base" cho khái niệm chung, "domain" cho riêng domain
    active_linking: true
    target_eligible: true
    aliases:                     # TẤT CẢ cách người ta gọi entity này
      - Heineken
      - heineken
      - "#Heineken"
    compact_aliases:             # Dạng viết liền/lowercase
      - heineken
    taxonomy_ids:
      - category.beer
    description: Thương hiệu bia Hà Lan.
    related_phrases:
      - bia Heineken
    domain_anchor_phrases:       # Cụm từ gắn chặt với domain này
      - heineken
    neighboring_entity_ids:      # Entity liên quan (cho ngữ cảnh đồ thị)
      - tiger
      - saigon_beer
    neighboring_aspect_ids:      # Aspect liên quan nhất đến entity
      - taste
      - price
      - quality
  # ... thêm entities

# Topics — chủ đề hội thoại mà hệ thống phân loại
topics:
  - topic_key: product_experience
    label: Trải nghiệm sản phẩm
    seed_phrases: [chất lượng, quality, ngon, dở, ...]
    related_aspect_ids: [taste, quality]
    related_issue_ids: [quality_problem]
    compatible_entity_types: [brand, product]
  # ...

# Tùy chọn
alias_contributions: []
noise_terms:
  - term: haha
    reason: low_information_social_reaction
```

### Quy tắc quan trọng cho ontology YAML

1. **Tham chiếu chéo phải hợp lệ.** `model_validator` trong `OntologyRegistry` kiểm tra:
   - `EntitySeed.taxonomy_ids` phải trỏ đến `taxonomy_nodes[].id` tồn tại
   - `EntitySeed.neighboring_entity_ids` phải trỏ đến `entities[].id` tồn tại
   - `EntitySeed.neighboring_aspect_ids` phải trỏ đến `aspect_categories[].id` tồn tại
   - `CategoryDefinition.linked_topic_keys` phải trỏ đến `topics[].topic_key` tồn tại
   - `CategoryDefinition.related_issue_ids` phải trỏ đến `issue_categories[].id` tồn tại
   - `CategoryDefinition.related_aspect_ids` phải trỏ đến `aspect_categories[].id` tồn tại
   - `TopicDefinition.related_entity_ids` phải trỏ đến `entities[].id` tồn tại
   - `TopicDefinition.related_taxonomy_ids` phải trỏ đến `taxonomy_nodes[].id` tồn tại
   - `TopicDefinition.related_aspect_ids` phải trỏ đến `aspect_categories[].id` tồn tại
   - `TopicDefinition.related_issue_ids` phải trỏ đến `issue_categories[].id` tồn tại

2. **Entity types** bắt buộc phải có tập chung: `brand`, `product`, `person`, `organization`, `location`, `facility`, `retailer`, `concept`.

3. **Intent categories** bắt buộc phải có tập chung: `question`, `complaint`, `commentary`, `praise`, `purchase_intent`, `compare`.

4. Giá trị **`knowledge_layer`**: `"base"` (khái niệm chung), `"domain"` (entity riêng domain), `"domain_overlay"` (ghi đè runtime).

5. **Aliases rất quan trọng** — chúng là cốt lõi của entity resolution. Cần bao gồm:
   - Tên chính thức, lỗi chính tả phổ biến, hashtags, viết tắt
   - Tiếng Việt có dấu và không dấu
   - `compact_aliases` cho dạng viết liền không dấu (ví dụ: "vinfast" cho "Vin Fast")

### Bước 2: Tạo file con trỏ domain

Tạo `config/domains/<domain_code>.yaml`:

```yaml
domain_code: "beer"
display_name: "Bia & Đồ uống"

ontology:
  path: "config/ontology/beer_vn.yaml"
  overlays: []                    # Đường dẫn YAML overlay tùy chọn

runtime:
  brand_names:
    - "Heineken"
    - "Tiger"
    - "Saigon Beer"
  topic_seeds:
    - "bia"
    - "beer"
  stop_entities: []

contract:
  domain_overlay: "domain-beer-vn"
```

### Bước 3: Kiểm tra tính hợp lệ của ontology

Chạy script Python để validate:

```python
import yaml
from internal.ontology.type import OntologyRegistry

with open("config/ontology/beer_vn.yaml") as f:
    data = yaml.safe_load(f)

registry = OntologyRegistry.model_validate(data)
print(f"Entities: {len(registry.entities)}")
print(f"Aspects:  {len(registry.aspect_categories)}")
print(f"Issues:   {len(registry.issue_categories)}")
print(f"Topics:   {len(registry.topics)}")
print(f"Aliases:  {len(registry.alias_map())}")
print("Validation thành công!")
```

Nếu tham chiếu chéo bị sai, Pydantic sẽ ném `ValidationError` với chi tiết lỗi.

### Bước 4: Trỏ config sang domain mới

Trong `config/config.yaml` (hoặc ConfigMap):

```yaml
ontology:
  domain_ontology_path: "config/ontology/beer_vn.yaml"
```

### Bước 5: Deploy

Xem phần [Build & Deploy](#build--deploy) bên dưới.

---

## Build & Deploy

### Yêu cầu

- Docker có buildx
- Truy cập được `registry.tantai.dev` (Harbor registry)
- Đã set `HARBOR_USERNAME` và `HARBOR_PASSWORD` trong biến môi trường
- `kubectl` đã cấu hình cho K3s cluster

### Docker build hai tầng

Service dùng build hai tầng để CI/CD nhanh:

| Image | Kích thước | Rebuild khi | Thời gian build |
|-------|-----------|-------------|----------------|
| `analysis-base:latest` | ~2GB | pyproject.toml/uv.lock thay đổi, PhoBERT model cập nhật | 10-20 phút |
| `analysis-consumer:latest` | +~50MB | Code ứng dụng thay đổi (bất kỳ .py hoặc .yaml trong apps/config/internal/pkg) | ~30 giây |

### Lệnh build

```bash
# Chạy từ thư mục gốc dự án (analysis-srv/)

# 1. Build base image (chỉ khi thay đổi deps)
./scripts/build-base.sh

# 2. Build consumer image (sau khi thay đổi code)
./scripts/build-consumer.sh
```

Cả hai script tự đăng nhập Harbor, build với `linux/amd64`, và push với cả tag theo thời gian (`YYMMDD-HHMMSS`) lẫn `latest`.

### Deploy lên K3s

```bash
# Apply ConfigMap (chứa toàn bộ YAML config bao gồm ontology/enrichment)
kubectl apply -f manifests/configmap.yaml

# Apply Deployment
kubectl apply -f apps/consumer/deployment.yaml

# Apply HPA (tùy chọn — cho autoscaling)
kubectl apply -f manifests/hpa.yaml

# Kiểm tra
kubectl -n smap get pods -l app=analysis-consumer
kubectl -n smap logs -f deploy/analysis-consumer
```

### Cập nhật image tag trong deployment

Sau khi build consumer image mới, cập nhật deployment:

```bash
# Cách A: Sửa deployment.yaml rồi apply lại
# Đổi image: registry.tantai.dev/smap/analysis-consumer:<tag-mới>
kubectl apply -f apps/consumer/deployment.yaml

# Cách B: Patch trực tiếp
kubectl -n smap set image deployment/analysis-consumer \
  analysis-consumer=registry.tantai.dev/smap/analysis-consumer:<tag-mới>

# Cách C: Nếu dùng tag :latest, restart để pull image mới
kubectl -n smap rollout restart deployment/analysis-consumer
```

---

## Tham chiếu cấu hình

Toàn bộ config nằm trong 1 file YAML được mount tại `/app/config/config.yaml` qua ConfigMap.

### Các stage của pipeline

```yaml
pipeline:
  enable_normalization: true    # Chuẩn hóa text, ánh xạ field
  enable_dedup: true            # Loại trùng bằng MinHash
  enable_spam: true             # Lọc spam/nhiễu
  enable_threads: true          # Ghép thread (comment cha-con)
  enable_nlp: true              # Sentiment, keywords, intent, impact
  enable_enrichment: true       # Làm giàu Entity + Semantic + Topic (MỚI)
  enable_review: false          # Tương lai: hàng đợi review thủ công
  enable_reporting: false       # Tương lai: tạo báo cáo
  enable_crisis: false          # Tương lai: phát hiện khủng hoảng
```

### Ontology

```yaml
ontology:
  # Đường dẫn đến file ontology domain tự chứa
  domain_ontology_path: "config/ontology/vinfast_vn.yaml"
```

### Các sub-stage của enrichment

```yaml
enrichment:
  entity_enabled: true           # Nhận diện entity qua alias map từ ontology
  semantic_enabled: true         # Phát hiện aspect/issue qua seed phrases
  topic_enabled: true            # Phân loại topic qua seed phrases + TF-IDF
  source_influence_enabled: true # Tính điểm ảnh hưởng nguồn
  semantic_full_enabled: true    # Suy luận ngữ nghĩa đầy đủ (aspect + issue + target)
```

### Domain registry

```yaml
domain_registry:
  domains_dir: "config/domains"    # Thư mục chứa file YAML mỗi domain
  fallback_domain: "_default"      # Domain dùng khi không khớp domain nào
```

---

## Enrichment Pipeline

Stage enrichment chạy sau NLP và tạo ra các facts có cấu trúc:

```
Văn bản đầu vào
  │
  ├─► Entity Enricher
  │     1. Xây alias_map từ ontology (alias entity → entity ID)
  │     2. Khớp ứng viên NER với alias_map → EntityResolutionFact
  │     3. Quét text thô tìm alias ontology không bắt được bởi NER
  │     4. Dự phòng: trích xuất regex cho ứng viên chưa giải quyết
  │
  ├─► Semantic Enricher
  │     1. Xây aspect_seeds và issue_seeds từ ontology CategoryDefinition.seed_phrases
  │     2. Khớp text với seed phrases → AspectOpinionHypothesis, IssueSignalHypothesis
  │     3. Xây TargetReference có căn cứ từ entity đã giải quyết
  │     4. Tạo TargetSentimentHypothesis cho sentiment cấp entity
  │
  └─► Topic Enricher
        1. Khớp mention với ontology TopicDefinition.seed_phrases
        2. Topic đã biết → TopicArtifactFact (confidence 0.75)
        3. Mention chưa biết → phân cụm TF-IDF → TopicArtifactFact
```

### Các loại fact được tạo ra

| Loại Fact | Nguồn | Mô tả |
|-----------|-------|-------|
| `EntityResolutionFact` | Entity enricher | Entity đã giải quyết với ID, confidence, resolution_kind |
| `AspectOpinionHypothesis` | Semantic enricher | Khía cạnh phát hiện được với polariry và bằng chứng |
| `IssueSignalHypothesis` | Semantic enricher | Tín hiệu vấn đề phát hiện được |
| `TargetSentimentHypothesis` | Semantic enricher | Sentiment cấp entity |
| `TopicArtifactFact` | Topic enricher | Topic đã phân loại với confidence |

---

## Xử lý sự cố

### Pod bị OOMKilled

Enrichment + PhoBERT cần nhiều bộ nhớ hơn pipeline NLP cũ. Giới hạn hiện tại:

- Requests: 1.5Gi memory, 500m CPU
- Limits: 4Gi memory, 2000m CPU

Nếu bị OOMKilled, tăng `resources.limits.memory` trong `deployment.yaml`.

### Lỗi validation ontology khi khởi động

Kiểm tra logs tìm Pydantic `ValidationError`. Nguyên nhân phổ biến:

- Tham chiếu chéo bị hỏng (ví dụ: entity tham chiếu taxonomy_id không tồn tại)
- Thiếu field bắt buộc trong entity hoặc category definition
- ID bị trùng

Sửa file ontology YAML rồi deploy lại.

### Không tạo được enrichment facts

1. Kiểm tra `pipeline.enable_enrichment: true` trong ConfigMap
2. Kiểm tra `enrichment.*_enabled: true` trong ConfigMap
3. Kiểm tra `ontology.domain_ontology_path` trỏ đến file YAML hợp lệ
4. Kiểm tra logs xem có lỗi load ontology khi khởi động không

### HPA không scale

- HPA yêu cầu `metrics-server` được cài trong cluster
- Kiểm tra: `kubectl -n smap get hpa analysis-consumer`
- `maxReplicas` nên `<=` số lượng Kafka partition (consumer vượt quá số partition sẽ ngồi chờ)

### Khởi động chậm (>60 giây)

Load model PhoBERT + SpaCy mất 30-60 giây khi cold start. `startupProbe` cho phép tối đa 120 giây. Nếu liên tục bị timeout, kiểm tra:

- Base image đã có sẵn model (`internal/model/phobert/phobert.onnx`)
- CPU requests đủ lớn (load model tốn CPU)
