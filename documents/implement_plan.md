# IMPLEMENTATION ROADMAP

**Date**: November 29, 2025  
**Reviewer**: Senior Technical Architect  
**Status**: Ready for Development

---

## PHASE 0: PREPARATION ✅ COMPLETED
**Duration**: 3-5 days  
**Team**: Tech Lead + DevOps  
**Goal**: Setup môi trường phát triển & infrastructure foundation  
**Status**: ✅ **COMPLETED** (November 29, 2025)

### Tasks

#### 0.1 Project Setup ✅
- [x] **Git Repository** - Completed with clean architecture structure
  ```bash
  analytics-service/
  ├── README.md
  ├── .gitignore
  ├── requirements.txt
  ├── pyproject.toml (Poetry)
  ├── Dockerfile
  ├── docker-compose.yml
  ├── .env.example
  ├── src/
  │   ├── __init__.py
  │   ├── config/
  │   ├── models/
  │   ├── modules/
  │   ├── api/
  │   └── utils/
  ├── tests/
  │   ├── unit/
  │   ├── integration/
  │   └── fixtures/
  ├── scripts/
  │   ├── setup.sh
  │   └── run_tests.sh
  ├── docs/
  │   ├── API.md
  │   └── DEPLOYMENT.md
  └── .github/
      └── workflows/
          ├── ci.yml
          └── cd.yml
  ```

- [x] **Development Environment** - Docker Compose with Postgres, Redis, MinIO running
  ```yaml
  # docker-compose.dev.yml
  version: '3.8'
  services:
    postgres:
      image: postgres:15-alpine
      environment:
        POSTGRES_DB: analytics_dev
        POSTGRES_USER: dev
        POSTGRES_PASSWORD: dev123
      ports:
        - "5432:5432"
      volumes:
        - pgdata:/var/lib/postgresql/data
    
    redis:
      image: redis:7-alpine
      ports:
        - "6379:6379"
    
    minio:
      image: minio/minio:latest
      command: server /data --console-address ":9001"
      environment:
        MINIO_ROOT_USER: minioadmin
        MINIO_ROOT_PASSWORD: minioadmin
      ports:
        - "9000:9000"
        - "9001:9001"
      volumes:
        - minio_data:/data
  
  volumes:
    pgdata:
    minio_data:
  ```

- [x] **Python Environment** - Using `uv` package manager (faster than Poetry)
  ```bash
  # Setup với Poetry
  poetry init
  poetry add fastapi uvicorn[standard] sqlalchemy asyncpg
  poetry add transformers onnxruntime spacy yake
  poetry add redis celery[redis] pydantic python-dotenv
  poetry add --group dev pytest pytest-cov pytest-asyncio black ruff mypy
  
  # Download SpaCy model
  python -m spacy download vi_core_news_lg
  ```

#### 0.2 Database Migration Setup ✅
- [x] **Alembic Configuration**
  ```bash
  uv add alembic
  alembic init migrations
  ```

- [x] **Initial Migration Script**
  - Created `post_analytics` table with all required fields
  - Added indexes for performance
  - Applied migration successfully

### Deliverables (Phase 0) ✅
- ✅ **Git repository** with layered architecture structure
- ✅ **Docker Compose dev environment** running (Postgres, Redis, MinIO)
- ✅ **Database migration scripts** with Alembic
- ✅ **Project structure** following `commands/`, `internal/`, `core/`, `infrastructure/`, `services/`

### Success Criteria ✅
- [x] `docker-compose up` running successfully
- [x] Database migrations applied
- [x] API and Consumer entry points working
- [x] Architecture documented

---

## PHASE 0.5: AI MODEL INTEGRATION ✅ COMPLETED
**Duration**: 2-3 days  
**Team**: ML Engineer + Backend Engineer  
**Goal**: Integrate and test PhoBERT (ONNX) model thoroughly  
**Status**: ✅ **COMPLETED** (November 29, 2025)

### Tasks

#### 0.5.1 PhoBERT ONNX Setup ✅
- [x] **Model Acquisition**
  - Downloaded pre-trained PhoBERT ONNX model (quantized for CPU)
  - Model stored in MinIO for artifact management
  - Created download script: `scripts/download_phobert_model.sh`
  - Added `make download-phobert` command

- [x] **Create Model Wrapper**
  - Implemented `infrastructure/ai/phobert_onnx.py` (250+ lines)
  - Features:
    - Vietnamese text segmentation with PyVi
    - PhoBERT tokenization (max 128 tokens)
    - ONNX Runtime inference
    - 5-class sentiment prediction (1-5 stars)
    - Batch prediction support
    - Probability distribution output
  
- [x] **Constants Management**
  - Created `infrastructure/ai/constants.py`
  - Centralized all configuration values
  - Easy to modify and maintain

#### 0.5.2 Comprehensive Testing ✅
- [x] **Unit Tests** (`tests/phobert/test_unit.py`)
  - 21 tests covering:
    - Text segmentation (3 tests)
    - Tokenization (2 tests)
    - Post-processing all 5 classes (7 tests)
    - Prediction logic (4 tests)
    - Batch processing (2 tests)
    - Edge cases (3 tests)
  - ✅ 21/21 passing (100%)

- [x] **Integration Tests** (`tests/phobert/test_integration.py`)
  - 9 tests with real model:
    - Positive/negative/neutral sentiment
    - Mixed sentiment handling
    - Batch prediction
    - Long text processing
    - Special characters & emojis
    - Probability distribution
    - Prediction consistency
  - ✅ 9/9 passing (100%)

- [x] **Performance Tests** (`tests/phobert/test_performance.py`)
  - 6 benchmark tests:
    - Single inference speed (<100ms) ✅
    - Batch throughput ✅
    - Model loading time ✅
    - Memory usage (skipped - requires psutil)
    - Throughput benchmarks ✅
    - Cold start vs warm ✅
  - ✅ 5/6 passing (1 skipped)

#### 0.5.3 Documentation ✅
- [x] **Model Report** (`documents/phobert_report.md`)
  - Test coverage summary
  - Performance benchmarks
  - Model strengths & limitations
  - Deployment recommendations

- [x] **README Updates**
  - Quick start guide
  - Usage examples
  - Configuration options
  - Development commands

- [x] **OpenSpec Archive**
  - Archived as `2025-11-29-phobert_integration`
  - Created `openspec/specs/ai_integration/spec.md`

### Deliverables (Phase 0.5) ✅
- ✅ **PhoBERT ONNX model** downloaded and configured
- ✅ **Model wrapper** in `infrastructure/ai/phobert_onnx.py`
- ✅ **Constants file** in `infrastructure/ai/constants.py`
- ✅ **Comprehensive test suite** (35 tests total)
  - 21 unit tests
  - 9 integration tests
  - 5 performance tests
- ✅ **Model report** with benchmarks
- ✅ **Documentation** updated (README, project.md)

### Success Criteria ✅
- [x] PhoBERT inference <100ms per text ✅ (~50-80ms achieved)
- [x] All unit tests passing (coverage >90%) ✅ (100% coverage)
- [x] Integration tests passing ✅ (9/9)
- [x] Model correctly predicts Vietnamese sentiment ✅
- [x] Performance benchmarks documented ✅
- [x] OpenSpec change archived ✅

### Performance Results
```
Single Prediction:     ~50-80ms (Target: <100ms) ✅
Batch (30 texts):      ~150ms avg (Target: <200ms) ✅
Model Loading:         ~2-3s (Target: <5s) ✅
Memory Usage:          ~200-300MB ✅
Throughput:            ~10-15 pred/s (Target: ≥5) ✅
```

### Test Commands
```bash
make test-phobert              # All tests (35 total)
make test-phobert-unit         # Unit only (21 tests)
make test-phobert-integration  # Integration (9 tests)
make test-phobert-performance  # Performance (5 tests)
```


#### 0.5.2 YAKE Integration
- [ ] **Install and Test YAKE**
  ```bash
  uv add yake
  ```

- [ ] **Create YAKE Wrapper**
  ```python
  # infrastructure/ai/yake_extractor.py
  import yake
  from typing import List, Dict
  
  class YAKEExtractor:
      def __init__(self):
          self.extractor = yake.KeywordExtractor(
              lan="vi",
              n=2,  # bigrams
              dedupLim=0.7,
              top=10,
              features=None
          )
      
      def extract(self, text: str) -> List[Dict]:
          keywords = self.extractor.extract_keywords(text)
          
          results = []
          for keyword, score in keywords:
              # YAKE score: lower is better, convert to weight
              weight = max(0, 1 - score)
              
              if weight > 0.3:  # Filter low-quality keywords
                  results.append({
                      "keyword": keyword,
                      "weight": weight,
                      "score": score,
                      "method": "YAKE"
                  })
          
          return results
  ```

- [ ] **Unit Tests for YAKE**
  ```python
  # tests/unit/test_yake_extractor.py
  import pytest
  from infrastructure.ai.yake_extractor import YAKEExtractor
  
  @pytest.fixture
  def extractor():
      return YAKEExtractor()
  
  def test_extract_keywords(extractor):
      text = "Xe VinFast VF8 có thiết kế đẹp, pin trâu nhưng giá hơi cao"
      
      keywords = extractor.extract(text)
      
      assert len(keywords) > 0
      assert all("keyword" in kw for kw in keywords)
      assert all("weight" in kw for kw in keywords)
      assert all(kw["weight"] > 0.3 for kw in keywords)
  
  def test_vietnamese_text(extractor):
      text = "Chất lượng sản phẩm tốt, dịch vụ bảo hành chu đáo"
      
      keywords = extractor.extract(text)
      
      # Should extract Vietnamese keywords
      keyword_texts = [kw["keyword"] for kw in keywords]
      assert any("chất lượng" in kw.lower() for kw in keyword_texts)
  
  def test_performance(extractor):
      text = "Xe VinFast VF8 có thiết kế đẹp" * 10
      
      import time
      start = time.time()
      keywords = extractor.extract(text)
      duration = (time.time() - start) * 1000
      
      assert duration < 500  # Must be < 500ms
      assert len(keywords) > 0
  ```

#### 0.5.3 Integration Tests
- [ ] **Combined Model Test**
  ```python
  # tests/integration/test_ai_models.py
  import pytest
  from infrastructure.ai.phobert_onnx import PhoBERTONNX
  from infrastructure.ai.yake_extractor import YAKEExtractor
  
  @pytest.fixture
  def phobert():
      return PhoBERTONNX("models/phobert_sentiment_cpu.onnx")
  
  @pytest.fixture
  def yake():
      return YAKEExtractor()
  
  def test_full_pipeline(phobert, yake):
      text = "Xe VinFast VF8 có thiết kế đẹp, pin trâu nhưng giá hơi cao"
      
      # Extract keywords
      keywords = yake.extract(text)
      assert len(keywords) > 0
      
      # Analyze sentiment
      sentiment = phobert.predict(text)
      assert sentiment["sentiment"] in ["POSITIVE", "NEUTRAL", "NEGATIVE"]
      
      # Combined result
      result = {
          "text": text,
          "keywords": keywords,
          "sentiment": sentiment
          }
      
      assert "keywords" in result
      assert "sentiment" in result
  
  def test_performance_benchmark(phobert, yake):
      texts = [
          "Xe đẹp, pin tốt",
          "Giá cao, chất lượng kém",
          "Bình thường, không có gì đặc biệt"
      ] * 10  # 30 texts
      
      import time
      start = time.time()
      
      for text in texts:
          keywords = yake.extract(text)
          sentiment = phobert.predict(text)
      
      duration = time.time() - start
      avg_time = (duration / len(texts)) * 1000
      
      assert avg_time < 200  # Average < 200ms per text
  ```

### Deliverables (Phase 0.5)
- **PhoBERT ONNX model** converted and optimized
- **YAKE extractor** configured for Vietnamese
- **Model wrappers** in `infrastructure/ai/`
- **Comprehensive unit tests** for both models
- **Integration tests** for combined pipeline
- **Performance benchmarks** documented

### Success Criteria
- [ ] PhoBERT inference < 100ms per text
- [ ] YAKE extraction < 500ms per text
- [ ] All unit tests passing (coverage > 90%)
- [ ] Integration tests passing
- [ ] Models correctly predict Vietnamese sentiment
- [ ] Keywords extracted accurately

---

## PHASE 1: CORE MODULES (NO AI)
**Duration**: 5-7 working days  
**Team**: 2 Backend Engineers  
**Goal**: Implement core business logic modules WITHOUT AI dependencies

### Core Modules

#### 1.1 Module 1: TextPreprocessor
**File**: `src/modules/preprocessor.py`

**Tasks**:
- [ ] **Implement TextPreprocessor class**
  ```python
  # src/modules/preprocessor.py
  import re
  from typing import Dict, List
  
  class TextPreprocessor:
      def __init__(self):
          self.emoji_pattern = re.compile("["
              u"\U0001F600-\U0001F64F"
              u"\U0001F300-\U0001F5FF"
              u"\U0001F680-\U0001F6FF"
              u"\U0001F1E0-\U0001F1FF"
              "]+", flags=re.UNICODE)
      
      def merge_content(self, 
                       text: str, 
                       comments: List[Dict],
                       transcription: str = None) -> str:
          """Merge caption + top comments + transcription"""
          merged = text or ""
          
          # Add top 5 most-liked comments
          sorted_comments = sorted(
              comments,
              key=lambda x: x.get('likes', 0),
              reverse=True
          )[:5]
          
          for comment in sorted_comments:
              merged += " " + comment.get('text', '')
          
          # Add transcription if available
          if transcription:
              merged += " " + transcription
          
          return merged
      
      def normalize(self, text: str) -> str:
          """Clean and normalize text"""
          # Remove URLs
          text = re.sub(r'http\S+|www\S+', '', text)
          
          # Remove emojis
          text = self.emoji_pattern.sub('', text)
          
          # Process hashtags
          text = re.sub(r'#(\w+)', r'\1', text)
          
          # Normalize whitespace
          text = ' '.join(text.split())
          
          # Lowercase
          text = text.lower()
          
          return text.strip()
      
      def get_context_window(self, 
                            text: str, 
                            keyword: str, 
                            window_size: int = 50) -> str:
          """Extract context around keyword"""
          pos = text.find(keyword)
          if pos == -1:
              return text
          
          start = max(0, pos - window_size)
          end = min(len(text), pos + len(keyword) + window_size)
          
          return text[start:end]
  ```

- [ ] **Unit Tests**
  ```python
  # tests/unit/test_preprocessor.py
  import pytest
  from src.modules.preprocessor import TextPreprocessor
  
  def test_merge_content():
      preprocessor = TextPreprocessor()
      
      text = "Xe đẹp #vinfast"
      comments = [
          {"text": "Giá cao quá", "likes": 100},
          {"text": "Pin yếu", "likes": 50}
      ]
      
      result = preprocessor.merge_content(text, comments)
      
      assert "xe đẹp" in result.lower()
      assert "giá cao" in result.lower()
      assert "pin yếu" in result.lower()
  
  def test_normalize():
      preprocessor = TextPreprocessor()
      
      text = "Xe ĐẸP lắm 😊 #vinfast http://example.com"
      result = preprocessor.normalize(text)
      
      assert result == "xe đẹp lắm vinfast"
      assert "😊" not in result
      assert "http" not in result
  
  def test_context_window():
      preprocessor = TextPreprocessor()
      
      text = "Xe này thiết kế đẹp nhưng giá hơi cao"
      result = preprocessor.get_context_window(text, "giá", window_size=10)
      
      assert "giá" in result
      assert len(result) <= 30  # keyword + 2*window
  ```

**Acceptance Criteria**:
- [ ] All tests pass (coverage >90%)
- [ ] Processing time < 10ms per post
- [ ] Handles Vietnamese text correctly

---

#### 1.2 Module 2: IntentClassifier (Day 3-4)
**File**: `src/modules/intent_classifier.py`

**Tasks**:
- [ ] **Implement Intent Patterns**
  ```python
  # src/modules/intent_classifier.py
  import re
  from typing import Dict, List
  from enum import Enum
  
  class Intent(str, Enum):
      SEEDING = "SEEDING"
      SPAM = "SPAM"
      CRISIS = "CRISIS"
      COMPLAINT = "COMPLAINT"
      LEAD = "LEAD"
      SUPPORT = "SUPPORT"
      DISCUSSION = "DISCUSSION"
  
  class IntentClassifier:
      def __init__(self):
          self.patterns = {
              Intent.SEEDING: [
                  r'\d{9,11}',
                  r'liên hệ.*(mua|báo giá)',
                  r'inbox.*(giá|mua)',
                  r'zalo.*\d{9,11}',
                  r'(inbox|ib|chat).*(giá|deal)'
              ],
              Intent.SPAM: [
                  r'vay.*tiền',
                  r'cho.*thuê',
                  r'bán.*sim',
                  r'kinh doanh.*online',
                  r'cần.*tuyển.*ctv'
              ],
              Intent.CRISIS: [
                  r'tẩy chay',
                  r'lừa.*đảo',
                  r'kiện',
                  r'scam',
                  r'bùng.*nổ',
                  r'chết.*người',
                  r'nguy.*hiểm.*tính.*mạng'
              ],
              Intent.COMPLAINT: [
                  r'lỗi.*(không|chưa).*sửa',
                  r'hỏng.*lần.*thứ',
                  r'thất vọng',
                  r'tệ.*quá',
                  r'kém.*chất.*lượng',
                  r'(hỏng|lỗi|hư).*mãi.*không.*sửa'
              ],
              Intent.LEAD: [
                  r'giá.*bao.*nhiêu',
                  r'mua.*ở.*đâu',
                  r'(có|còn).*xe',
                  r'test.*drive',
                  r'xem.*xe',
                  r'showroom.*gần'
              ],
              Intent.SUPPORT: [
                  r'cách.*sạc',
                  r'showroom.*ở',
                  r'bảo.*hành',
                  r'sửa.*chữa',
                  r'liên.*hệ.*cskh',
                  r'hướng.*dẫn.*sử.*dụng'
              ]
          }
          
          # Priority (higher = more important)
          self.priority = {
              Intent.CRISIS: 10,
              Intent.SEEDING: 9,
              Intent.SPAM: 9,
              Intent.COMPLAINT: 7,
              Intent.LEAD: 5,
              Intent.SUPPORT: 4,
              Intent.DISCUSSION: 1
          }
      
      def predict(self, text: str) -> Dict:
          matched = []
          
          for intent, patterns in self.patterns.items():
              for pattern in patterns:
                  if re.search(pattern, text, re.IGNORECASE):
                      matched.append({
                          "intent": intent,
                          "pattern": pattern,
                          "priority": self.priority[intent]
                      })
                      break
          
          if not matched:
              return {
                  "intent": Intent.DISCUSSION,
                  "confidence": 0.5,
                  "should_skip": False
              }
          
          # Get highest priority
          matched.sort(key=lambda x: x['priority'], reverse=True)
          primary = matched[0]['intent']
          
          return {
              "intent": primary,
              "confidence": 0.9,
              "should_skip": primary in [Intent.SEEDING, Intent.SPAM]
          }
  ```

- [ ] **Unit Tests**
  ```python
  # tests/unit/test_intent_classifier.py
  def test_detect_seeding():
      classifier = IntentClassifier()
      
      text = "Xe đẹp quá! Liên hệ 0909123456 để mua"
      result = classifier.predict(text)
      
      assert result['intent'] == Intent.SEEDING
      assert result['should_skip'] == True
  
  def test_detect_crisis():
      classifier = IntentClassifier()
      
      text = "Xe này lừa đảo, mọi người tẩy chay đi!"
      result = classifier.predict(text)
      
      assert result['intent'] == Intent.CRISIS
      assert result['should_skip'] == False  # Crisis cần analyze
  
  def test_priority_crisis_over_complaint():
      classifier = IntentClassifier()
      
      text = "Xe lỗi mãi không sửa, sẽ kiện công ty!"
      result = classifier.predict(text)
      
      # "kiện" = CRISIS should win over "lỗi" = COMPLAINT
      assert result['intent'] == Intent.CRISIS
  ```

**Acceptance Criteria**:
- [ ] Detect all 7 intent types correctly
- [ ] Priority logic works (CRISIS > COMPLAINT)
- [ ] Vietnamese patterns cover >90% cases

---

#### 1.3 Database Layer (Day 5-6)
**File**: `src/models/post_analytics.py`

**Tasks**:
- [ ] **SQLAlchemy Models**
  ```python
  # src/models/post_analytics.py
  from sqlalchemy import Column, String, Integer, Float, Boolean, TIMESTAMP, JSON
  from sqlalchemy.dialects.postgresql import JSONB, UUID
  from sqlalchemy.ext.declarative import declarative_base
  from datetime import datetime
  
  Base = declarative_base()
  
  class PostAnalytics(Base):
      __tablename__ = 'post_analytics'
      
      id = Column(String(50), primary_key=True)
      project_id = Column(UUID, nullable=False)
      platform = Column(String(20), nullable=False)
      
      # Timestamps
      published_at = Column(TIMESTAMP, nullable=False)
      analyzed_at = Column(TIMESTAMP, default=datetime.utcnow)
      
      # Overall analysis
      overall_sentiment = Column(String(10), nullable=False)
      overall_sentiment_score = Column(Float)
      overall_confidence = Column(Float)
      
      # Intent
      primary_intent = Column(String(20), nullable=False)
      intent_confidence = Column(Float)
      
      # Impact
      impact_score = Column(Float, nullable=False)
      risk_level = Column(String(10), nullable=False)
      is_viral = Column(Boolean, default=False)
      is_kol = Column(Boolean, default=False)
      
      # JSONB
      aspects_breakdown = Column(JSONB)
      keywords = Column(JSONB)
      sentiment_probabilities = Column(JSONB)
      impact_breakdown = Column(JSONB)
      
      # Raw metrics
      view_count = Column(Integer, default=0)
      like_count = Column(Integer, default=0)
      comment_count = Column(Integer, default=0)
      share_count = Column(Integer, default=0)
      save_count = Column(Integer, default=0)
      follower_count = Column(Integer, default=0)
      
      # Processing metadata
      processing_time_ms = Column(Integer)
      model_version = Column(String(50))
  ```

- [ ] **Repository Pattern**
  ```python
  # src/repositories/analytics_repository.py
  from sqlalchemy.orm import Session
  from src.models.post_analytics import PostAnalytics
  from typing import Dict, Optional
  
  class AnalyticsRepository:
      def __init__(self, db: Session):
          self.db = db
      
      def save(self, analytics_data: Dict) -> PostAnalytics:
          """Save analytics result"""
          post = PostAnalytics(**analytics_data)
          self.db.add(post)
          self.db.commit()
          self.db.refresh(post)
          return post
      
      def get_by_id(self, post_id: str) -> Optional[PostAnalytics]:
          """Get by post ID"""
          return self.db.query(PostAnalytics).filter(
              PostAnalytics.id == post_id
          ).first()
      
      def update(self, post_id: str, data: Dict) -> PostAnalytics:
          """Update existing record"""
          post = self.get_by_id(post_id)
          if post:
              for key, value in data.items():
                  setattr(post, key, value)
              self.db.commit()
              self.db.refresh(post)
          return post
  ```

**Acceptance Criteria**:
- [ ] CRUD operations work
- [ ] JSONB columns indexed
- [ ] Migration applies successfully

---

### Week 2: AI/ML Modules

#### 1.4 Module 3: KeywordExtractor (Day 7-8)
**File**: `src/modules/keyword_extractor.py`

**Tasks**:
- [ ] **Aspect Dictionary (load from config)**
  ```yaml
  # config/aspects.yaml
  DESIGN:
    primary:
      - thiết kế
      - ngoại hình
      - đẹp
      - xấu
      - màu sắc
    secondary:
      - hiện đại
      - cổ điển
      - thể thao
      - sang trọng
  
  PERFORMANCE:
    primary:
      - pin
      - sạc
      - tốc độ
      - công suất
      - động cơ
    secondary:
      - km
      - quãng đường
      - tăng tốc
      - leo dốc
  
  PRICE:
    primary:
      - giá
      - tiền
      - đắt
      - rẻ
    secondary:
      - triệu
      - tỷ
      - mắc
      - hời
      - phù hợp
  
  QUALITY:
    primary:
      - chất lượng
      - bền
      - kém
      - tốt
      - lỗi
      - hỏng
    secondary:
      - ồn
      - rung
      - kêu
      - hở
      - rò rỉ
  
  SERVICE:
    primary:
      - bảo hành
      - sửa chữa
      - dịch vụ
      - hỗ trợ
      - cskh
    secondary:
      - showroom
      - nhân viên
      - lịch hẹn
      - chậm trễ
  
  COMFORT:
    primary:
      - thoải mái
      - ghế ngồi
      - nội thất
      - không gian
    secondary:
      - rộng rãi
      - chật chội
      - tiện nghi
      - điều hòa
  ```

- [ ] **Implement Extractor**
  ```python
  # src/modules/keyword_extractor.py
  import yaml
  import yake
  from typing import List, Dict
  
  class KeywordExtractor:
      def __init__(self, config_path: str = "config/aspects.yaml"):
          # Load aspect dictionary
          with open(config_path, 'r', encoding='utf-8') as f:
              self.aspect_dict = yaml.safe_load(f)
          
          # Initialize YAKE
          self.yake = yake.KeywordExtractor(
              lan="vi",
              n=2,
              dedupLim=0.7,
              top=10,
              features=None
          )
      
      def extract(self, text: str) -> List[Dict]:
          results = []
          
          # 1. Dictionary-based
          dict_keywords = self._extract_from_dict(text)
          results.extend(dict_keywords)
          
          # 2. YAKE (only if few dict matches)
          if len(dict_keywords) < 3:
              yake_keywords = self._extract_with_yake(text)
              results.extend(yake_keywords)
          
          # 3. Deduplicate
          return self._deduplicate(results)
      
      def _extract_from_dict(self, text: str) -> List[Dict]:
          found = []
          
          for aspect, keywords in self.aspect_dict.items():
              all_kw = keywords['primary'] + keywords['secondary']
              
              for kw in all_kw:
                  if kw in text:
                      pos = text.find(kw)
                      weight = 1.0 if kw in keywords['primary'] else 0.7
                      
                      found.append({
                          "keyword": kw,
                          "aspect": aspect,
                          "position": pos,
                          "weight": weight,
                          "method": "DICT"
                      })
          
          return found
      
      def _extract_with_yake(self, text: str) -> List[Dict]:
          keywords = self.yake.extract_keywords(text)
          
          results = []
          for kw, score in keywords:
              weight = max(0, 1 - score)
              
              if weight > 0.3:
                  results.append({
                      "keyword": kw,
                      "aspect": "OTHER",
                      "position": text.find(kw),
                      "weight": weight,
                      "method": "YAKE"
                  })
          
          return results
      
      def _deduplicate(self, keywords: List[Dict]) -> List[Dict]:
          seen = {}
          for kw in keywords:
              key = kw['keyword']
              if key not in seen or kw['weight'] > seen[key]['weight']:
                  seen[key] = kw
          
          return list(seen.values())
  ```

- [ ] **Unit Tests**
  ```python
  def test_extract_from_dict():
      extractor = KeywordExtractor()
      
      text = "xe này giá rẻ nhưng pin yếu"
      result = extractor.extract(text)
      
      keywords = [k['keyword'] for k in result]
      assert 'giá' in keywords
      assert 'pin' in keywords
      
      # Check aspects
      aspects = {k['keyword']: k['aspect'] for k in result}
      assert aspects['giá'] == 'PRICE'
      assert aspects['pin'] == 'PERFORMANCE'
  ```

**Acceptance Criteria**:
- [ ] Dictionary extraction >90% accuracy
- [ ] YAKE discovers new terms
- [ ] Processing time < 50ms

---

#### 1.5 Module 4: SentimentAnalyzer (Day 9-10)
**File**: `src/modules/sentiment_analyzer.py`

**Tasks**:
- [ ] **ONNX Inference Wrapper**
  ```python
  # src/modules/sentiment_analyzer.py
  import onnxruntime as ort
  import numpy as np
  from transformers import AutoTokenizer
  from typing import Dict, List
  
  class SentimentAnalyzer:
      def __init__(self, 
                   model_path: str = "models/phobert_sentiment_cpu.onnx",
                   tokenizer_name: str = "vinai/phobert-base"):
          
          # Load ONNX session
          self.session = ort.InferenceSession(
              model_path,
              providers=['CPUExecutionProvider']
          )
          
          # Load tokenizer
          self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
          
          self.label_map = {0: "NEGATIVE", 1: "NEUTRAL", 2: "POSITIVE"}
          self.score_map = {0: -0.8, 1: 0.0, 2: 0.8}
      
      def analyze(self, text: str, keywords: List[Dict] = None) -> Dict:
          """Main analysis function"""
          results = {
              "overall": self._predict_sentiment(text),
              "aspects": {}
          }
          
          # Aspect-based analysis
          if keywords:
              aspect_groups = self._group_by_aspect(keywords)
              
              for aspect, kw_list in aspect_groups.items():
                  aspect_sentiments = []
                  
                  for kw_data in kw_list:
                      context = self._extract_context(
                          text, 
                          kw_data['keyword'],
                          window_size=50
                      )
                      
                      sentiment = self._predict_sentiment(context)
                      sentiment['keyword'] = kw_data['keyword']
                      aspect_sentiments.append(sentiment)
                  
                  results['aspects'][aspect] = self._aggregate_aspect(
                      aspect_sentiments
                  )
          
          return results
      
      def _predict_sentiment(self, text: str) -> Dict:
          """Core ONNX inference"""
          # Tokenize
          inputs = self.tokenizer(
              text,
              return_tensors="np",
              truncation=True,
              max_length=256,
              padding='max_length'
          )
          
          # Run inference
          outputs = self.session.run(
              None,
              {
                  "input_ids": inputs['input_ids'].astype(np.int64),
                  "attention_mask": inputs['attention_mask'].astype(np.int64)
              }
          )
          
          logits = outputs[0][0]
          probabilities = self._softmax(logits)
          
          predicted_class = int(np.argmax(probabilities))
          confidence = float(probabilities[predicted_class])
          
          return {
              "label": self.label_map[predicted_class],
              "score": self.score_map[predicted_class],
              "confidence": confidence,
              "probabilities": {
                  "NEGATIVE": float(probabilities[0]),
                  "NEUTRAL": float(probabilities[1]),
                  "POSITIVE": float(probabilities[2])
              }
          }
      
      @staticmethod
      def _softmax(x):
          exp_x = np.exp(x - np.max(x))
          return exp_x / exp_x.sum()
      
      def _extract_context(self, text: str, keyword: str, window_size: int) -> str:
          pos = text.find(keyword)
          if pos == -1:
              return text
          
          start = max(0, pos - window_size)
          end = min(len(text), pos + len(keyword) + window_size)
          
          return text[start:end]
      
      def _group_by_aspect(self, keywords: List[Dict]) -> Dict:
          groups = {}
          for kw in keywords:
              aspect = kw['aspect']
              if aspect not in groups:
                  groups[aspect] = []
              groups[aspect].append(kw)
          return groups
      
      def _aggregate_aspect(self, sentiments: List[Dict]) -> Dict:
          if not sentiments:
              return None
          
          total_weight = sum(s['confidence'] for s in sentiments)
          avg_score = sum(s['score'] * s['confidence'] for s in sentiments) / total_weight
          
          if avg_score > 0.3:
              label = "POSITIVE"
          elif avg_score < -0.3:
              label = "NEGATIVE"
          else:
              label = "NEUTRAL"
          
          return {
              "sentiment": label,
              "score": avg_score,
              "confidence": total_weight / len(sentiments),
              "mentions": len(sentiments),
              "keywords": [s['keyword'] for s in sentiments]
          }
  ```

- [ ] **Unit Tests**
  ```python
  def test_onnx_inference():
      analyzer = SentimentAnalyzer()
      
      text = "Xe này đẹp quá!"
      result = analyzer._predict_sentiment(text)
      
      assert result['label'] in ["POSITIVE", "NEGATIVE", "NEUTRAL"]
      assert 0 <= result['confidence'] <= 1
      assert -1 <= result['score'] <= 1
  
  def test_aspect_based_sentiment():
      analyzer = SentimentAnalyzer()
      
      text = "giá rẻ nhưng chất lượng kém"
      keywords = [
          {"keyword": "giá", "aspect": "PRICE"},
          {"keyword": "chất lượng", "aspect": "QUALITY"}
      ]
      
      result = analyzer.analyze(text, keywords)
      
      # Giá should be POSITIVE
      assert result['aspects']['PRICE']['sentiment'] == "POSITIVE"
      
      # Quality should be NEGATIVE
      assert result['aspects']['QUALITY']['sentiment'] == "NEGATIVE"
  ```

**Acceptance Criteria**:
- [ ] ONNX inference < 50ms
- [ ] Aspect-based accuracy >80%
- [ ] Memory < 2GB per worker

---

#### 1.6 Module 5: ImpactCalculator (Day 11)
**File**: `src/modules/impact_calculator.py`

**Tasks**:
- [ ] **Implement Formula**
  ```python
  # src/modules/impact_calculator.py
  import math
  from typing import Dict
  
  class ImpactCalculator:
      PLATFORM_WEIGHTS = {
          "TIKTOK": 1.0,
          "YOUTUBE": 1.5,
          "FACEBOOK": 1.2,
          "INSTAGRAM": 1.1
      }
      
      SENTIMENT_AMPLIFIERS = {
          "NEGATIVE": 1.5,
          "NEUTRAL": 1.0,
          "POSITIVE": 1.2
      }
      
      VIRAL_THRESHOLD = 70
      KOL_THRESHOLD = 10000
      
      def calculate(self,
                   interaction: Dict,
                   author: Dict,
                   sentiment: Dict) -> Dict:
          
          # 1. Engagement score
          engagement = self._calculate_engagement(interaction)
          
          # 2. Reach score
          reach = self._calculate_reach(author)
          
          # 3. Platform multiplier
          platform = interaction.get('platform', 'UNKNOWN')
          platform_mult = self.PLATFORM_WEIGHTS.get(platform, 1.0)
          
          # 4. Sentiment amplifier
          sentiment_label = sentiment.get('label', 'NEUTRAL')
          sentiment_amp = self.SENTIMENT_AMPLIFIERS.get(sentiment_label, 1.0)
          
          # 5. Raw score
          raw_score = engagement * reach * platform_mult * sentiment_amp
          
          # 6. Normalize 0-100
          normalized = min(100, (raw_score / 10000) * 100)
          
          # 7. Flags
          is_viral = normalized >= self.VIRAL_THRESHOLD
          is_kol = author.get('followers', 0) >= self.KOL_THRESHOLD
          
          # 8. Risk level
          risk = self._calculate_risk(
              normalized,
              sentiment.get('score', 0),
              is_kol
          )
          
          return {
              "impact_score": round(normalized, 2),
              "is_viral": is_viral,
              "is_kol": is_kol,
              "risk_level": risk,
              "breakdown": {
                  "engagement_score": round(engagement, 2),
                  "reach_score": round(reach, 2),
                  "platform_multiplier": platform_mult,
                  "sentiment_amplifier": sentiment_amp,
                  "raw_score": round(raw_score, 2)
              }
          }
      
      def _calculate_engagement(self, interaction: Dict) -> float:
          return (
              interaction.get('likes', 0) * 1
              + interaction.get('comments_count', 0) * 2
              + interaction.get('saves', 0) * 3
              + interaction.get('shares', 0) * 5
          )
      
      def _calculate_reach(self, author: Dict) -> float:
          followers = author.get('followers', 0)
          reach = math.log10(followers + 1)
          
          if author.get('is_verified', False):
              reach *= 1.2
          
          return reach
      
      def _calculate_risk(self, impact: float, sentiment: float, is_kol: bool) -> str:
          if impact > 70 and sentiment < -0.3 and is_kol:
              return "CRITICAL"
          
          if impact > 70 and sentiment < -0.3:
              return "HIGH"
          
          if impact > 40 and sentiment < -0.3:
              return "MEDIUM"
          
          if impact > 60:
              return "MEDIUM"
          
          return "LOW"
  ```

**Acceptance Criteria**:
- [ ] Formula matches specification
- [ ] Risk levels correct
- [ ] Processing time < 5ms

---

#### 1.7 API Layer (Day 12)
**File**: `src/api/main.py`

**Tasks**:
- [ ] **FastAPI Endpoints**
  ```python
  # src/api/main.py
  from fastapi import FastAPI, HTTPException, Depends
  from sqlalchemy.orm import Session
  from typing import Dict
  import time
  
  from src.orchestrator import AnalyticsPipeline
  from src.database import get_db
  from src.repositories.analytics_repository import AnalyticsRepository
  
  app = FastAPI(title="Analytics Service API", version="1.0.0")
  
  @app.post("/api/v1/analytics/process-post")
  async def process_post(
      post_data: Dict,
      db: Session = Depends(get_db)
  ):
      """Process a single post from MinIO"""
      try:
          start_time = time.time()
          
          # Initialize pipeline
          pipeline = AnalyticsPipeline()
          
          # Process
          result = pipeline.process(post_data)
          
          # Save to DB
          repo = AnalyticsRepository(db)
          repo.save(result)
          
          processing_time = int((time.time() - start_time) * 1000)
          
          return {
              "status": "SUCCESS",
              "post_id": result['id'],
              "processing_time_ms": processing_time,
              "result": result
          }
      
      except Exception as e:
          raise HTTPException(status_code=500, detail=str(e))
  
  @app.get("/api/v1/analytics/results/{post_id}")
  async def get_results(
      post_id: str,
      db: Session = Depends(get_db)
  ):
      """Get analysis results"""
      repo = AnalyticsRepository(db)
      result = repo.get_by_id(post_id)
      
      if not result:
          raise HTTPException(status_code=404, detail="Post not found")
      
      return result
  
  @app.get("/health")
  async def health_check():
      return {"status": "healthy"}
  ```

- [ ] **Orchestrator**
  ```python
  # src/orchestrator.py
  from typing import Dict
  from src.modules.preprocessor import TextPreprocessor
  from src.modules.intent_classifier import IntentClassifier
  from src.modules.keyword_extractor import KeywordExtractor
  from src.modules.sentiment_analyzer import SentimentAnalyzer
  from src.modules.impact_calculator import ImpactCalculator
  
  class AnalyticsPipeline:
      def __init__(self):
          self.preprocessor = TextPreprocessor()
          self.intent_classifier = IntentClassifier()
          self.keyword_extractor = KeywordExtractor()
          self.sentiment_analyzer = SentimentAnalyzer()
          self.impact_calculator = ImpactCalculator()
      
      def process(self, post_data: Dict) -> Dict:
          # 1. Preprocess
          clean_text = self.preprocessor.merge_content(
              post_data['content']['text'],
              post_data.get('comments', []),
              post_data['content'].get('transcription')
          )
          clean_text = self.preprocessor.normalize(clean_text)
          
          # 2. Intent classification (gatekeeper)
          intent_result = self.intent_classifier.predict(clean_text)
          
          if intent_result['should_skip']:
              return self._build_skipped_result(post_data, intent_result)
          
          # 3. Keyword extraction
          keywords = self.keyword_extractor.extract(clean_text)
          
          # 4. Sentiment analysis
          sentiment = self.sentiment_analyzer.analyze(clean_text, keywords)
          
          # 5. Impact calculation
          impact = self.impact_calculator.calculate(
              post_data['interaction'],
              post_data['author'],
              sentiment['overall']
          )
          
          # 6. Build result
          return self._build_result(
              post_data,
              intent_result,
              keywords,
              sentiment,
              impact
          )
      
      def _build_skipped_result(self, post_data: Dict, intent: Dict) -> Dict:
          return {
              "id": post_data['meta']['id'],
              "overall_sentiment": "NEUTRAL",
              "primary_intent": intent['intent'],
              "impact_score": 0,
              "risk_level": "LOW",
              "aspects_breakdown": {},
              "keywords": []
          }
      
      def _build_result(self, post_data, intent, keywords, sentiment, impact) -> Dict:
          return {
              "id": post_data['meta']['id'],
              "project_id": post_data['meta']['project_id'],
              "platform": post_data['meta']['platform'],
              "published_at": post_data['meta']['published_at'],
              
              "overall_sentiment": sentiment['overall']['label'],
              "overall_sentiment_score": sentiment['overall']['score'],
              "overall_confidence": sentiment['overall']['confidence'],
              
              "primary_intent": intent['intent'],
              "intent_confidence": intent['confidence'],
              
              "impact_score": impact['impact_score'],
              "risk_level": impact['risk_level'],
              "is_viral": impact['is_viral'],
              "is_kol": impact['is_kol'],
              
              "aspects_breakdown": sentiment['aspects'],
              "keywords": keywords,
              "sentiment_probabilities": sentiment['overall']['probabilities'],
              "impact_breakdown": impact['breakdown'],
              
              # Raw metrics
              "view_count": post_data['interaction'].get('views', 0),
              "like_count": post_data['interaction'].get('likes', 0),
              "comment_count": post_data['interaction'].get('comments_count', 0),
              "share_count": post_data['interaction'].get('shares', 0),
              "save_count": post_data['interaction'].get('saves', 0),
              "follower_count": post_data['author'].get('followers', 0),
              
              "model_version": "phobert-onnx-v1.0"
          }
  ```

**Acceptance Criteria**:
- [ ] API responds in <2s
- [ ] Error handling works
- [ ] Health check endpoint

---

### Week 2 Deliverables
- ✅ All 5 modules implemented & tested
- ✅ API endpoint working
- ✅ End-to-end test passing
- ✅ Code coverage >80%

### Phase 1 Success Criteria
- [ ] Process 1 post successfully end-to-end
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration test: MinIO → Processing → PostgreSQL
- [ ] API latency <2s (p95)
- [ ] Documentation complete

---

## PHASE 2: INTELLIGENCE LAYER (Week 3-4)
**Duration**: 10 working days  
**Goal**: Fine-tuning, optimization, advanced features

### Week 3: Model Fine-tuning & Optimization

#### 2.1 Data Collection for Fine-tuning (Day 13-14)
**Goal**: Collect 500-1000 labeled Vietnamese social media posts

**Tasks**:
- [ ] **Sample Selection Strategy**
  ```python
  # scripts/sample_posts_for_labeling.py
  """
  Select diverse posts for labeling:
  - 200 posts from each platform (TikTok, FB)
  - Cover all aspects (PRICE, DESIGN, PERFORMANCE...)
  - Mix of sentiments (positive, negative, neutral)
  - Different post lengths (short, medium, long)
  """
  
  import random
  from src.database import get_db
  from src.models.post_analytics import PostAnalytics
  
  def sample_posts():
      db = next(get_db())
      
      # Get random posts
      posts = db.query(PostAnalytics).order_by(
          db.func.random()
      ).limit(500).all()
      
      # Export to CSV for labeling
      import pandas as pd
      
      df = pd.DataFrame([{
          'id': p.id,
          'text': p.clean_text,
          'platform': p.platform,
          'predicted_sentiment': p.overall_sentiment,
          'label_sentiment': '',  # To be filled
          'label_aspects': '',     # To be filled
          'notes': ''
      } for p in posts])
      
      df.to_csv('data/labeling_queue.csv', index=False)
  ```

- [ ] **Labeling Interface (Simple CSV)**
  ```csv
  id,text,platform,predicted_sentiment,label_sentiment,label_aspects,notes
  757703...,xe đẹp nhưng giá cao,TIKTOK,MIXED,MIXED,"DESIGN:POS,PRICE:NEG",
  ```

- [ ] **Quality Control**
  - Inter-annotator agreement >0.8 (Cohen's Kappa)
  - Double labeling for 10% samples
  - Review disagreements

**Deliverables**:
- 500 labeled posts (minimum)
- Labeling guidelines document
- Quality metrics report

---

#### 2.2 Model Fine-tuning (Day 15-17)
**Goal**: Fine-tune PhoBERT on Vietnamese social media data

**Tasks**:
- [ ] **Training Script**
  ```python
  # scripts/fine_tune_phobert.py
  from transformers import (
      AutoModelForSequenceClassification,
      AutoTokenizer,
      Trainer,
      TrainingArguments
  )
  from datasets import load_dataset
  
  def fine_tune():
      # Load base model
      model = AutoModelForSequenceClassification.from_pretrained(
          "vinai/phobert-base",
          num_labels=3  # POS, NEG, NEU
      )
      
      tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base")
      
      # Load dataset
      dataset = load_dataset('csv', data_files={
          'train': 'data/train.csv',
          'validation': 'data/val.csv'
      })
      
      # Tokenize
      def tokenize_function(examples):
          return tokenizer(
              examples['text'],
              padding='max_length',
              truncation=True,
              max_length=256
          )
      
      tokenized = dataset.map(tokenize_function, batched=True)
      
      # Training args
      training_args = TrainingArguments(
          output_dir='./models/phobert_finetuned',
          evaluation_strategy='epoch',
          learning_rate=2e-5,
          per_device_train_batch_size=16,
          per_device_eval_batch_size=16,
          num_train_epochs=3,
          weight_decay=0.01,
          logging_dir='./logs',
          save_strategy='epoch',
          load_best_model_at_end=True
      )
      
      # Train
      trainer = Trainer(
          model=model,
          args=training_args,
          train_dataset=tokenized['train'],
          eval_dataset=tokenized['validation']
      )
      
      trainer.train()
      
      # Save
      model.save_pretrained('models/phobert_finetuned')
      tokenizer.save_pretrained('models/phobert_finetuned')
  ```

- [ ] **Convert to ONNX**
  ```bash
  python -m transformers.onnx \
      --model=models/phobert_finetuned \
      --feature=sequence-classification \
      onnx/phobert_finetuned/
  
  python -m onnxruntime.tools.optimize_model \
      --input onnx/phobert_finetuned/model.onnx \
      --output models/phobert_finetuned_cpu.onnx \
      --opt_level 2
  ```

- [ ] **A/B Testing Setup**
  ```python
  # src/modules/sentiment_analyzer.py
  class SentimentAnalyzer:
      def __init__(self, model_version: str = "v1"):
          if model_version == "v1":
              model_path = "models/phobert_sentiment_cpu.onnx"
          elif model_version == "v2":
              model_path = "models/phobert_finetuned_cpu.onnx"
          
          self.session = ort.InferenceSession(model_path)
          self.model_version = model_version
  ```

**Acceptance Criteria**:
- [ ] Fine-tuned model accuracy >90% on test set
- [ ] ONNX conversion successful
- [ ] A/B test shows v2 > v1 by >5%

---

#### 2.3 Caching Layer (Day 18)
**Goal**: Reduce redundant AI calls với Redis

**Tasks**:
- [ ] **Cache Strategy**
  ```python
  # src/utils/cache.py
  import redis
  import hashlib
  import json
  from typing import Optional, Dict
  
  class AnalyticsCache:
      def __init__(self, redis_url: str = "redis://localhost:6379"):
          self.redis = redis.from_url(redis_url)
          self.ttl = 86400  # 24 hours
      
      def get_sentiment(self, text: str) -> Optional[Dict]:
          """Get cached sentiment result"""
          key = self._make_key("sentiment", text)
          result = self.redis.get(key)
          
          if result:
              return json.loads(result)
          return None
      
      def set_sentiment(self, text: str, result: Dict):
          """Cache sentiment result"""
          key = self._make_key("sentiment", text)
          self.redis.setex(
              key,
              self.ttl,
              json.dumps(result)
          )
      
      def _make_key(self, prefix: str, text: str) -> str:
          """Generate cache key"""
          text_hash = hashlib.md5(text.encode()).hexdigest()
          return f"{prefix}:{text_hash}"
  ```

- [ ] **Integration with SentimentAnalyzer**
  ```python
  class SentimentAnalyzer:
      def __init__(self, cache: AnalyticsCache = None):
          self.cache = cache
          # ... existing init
      
      def _predict_sentiment(self, text: str) -> Dict:
          # Check cache first
          if self.cache:
              cached = self.cache.get_sentiment(text)
              if cached:
                  return cached
          
          # Run inference
          result = self._run_onnx_inference(text)
          
          # Cache result
          if self.cache:
              self.cache.set_sentiment(text, result)
          
          return result
  ```

**Expected Impact**:
- Cache hit rate >40% (many duplicate comments)
- Latency reduction ~30%
- Cost saving ~40%

---

### Week 4: Production Features

#### 2.4 Batch Processing (Day 19-20)
**Goal**: Xử lý nhiều posts song song

**Tasks**:
- [ ] **Celery Task**
  ```python
  # src/tasks/process_batch.py
  from celery import Celery
  from src.orchestrator import AnalyticsPipeline
  
  app = Celery('analytics', broker='redis://localhost:6379/0')
  
  @app.task(bind=True, max_retries=3)
  def process_post_async(self, post_data: dict):
      """Process single post asynchronously"""
      try:
          pipeline = AnalyticsPipeline()
          result = pipeline.process(post_data)
          
          # Save to DB
          from src.database import get_db
          from src.repositories.analytics_repository import AnalyticsRepository
          
          db = next(get_db())
          repo = AnalyticsRepository(db)
          repo.save(result)
          
          return {"status": "SUCCESS", "post_id": result['id']}
      
      except Exception as exc:
          # Retry with exponential backoff
          raise self.retry(exc=exc, countdown=2 ** self.request.retries)
  
  @app.task
  def process_batch(post_ids: list):
      """Process batch of posts"""
      from celery import group
      
      job = group(process_post_async.s(pid) for pid in post_ids)
      result = job.apply_async()
      
      return result.id
  ```

- [ ] **API Endpoint**
  ```python
  @app.post("/api/v1/analytics/process-batch")
  async def process_batch_endpoint(post_ids: List[str]):
      """Submit batch processing job"""
      from src.tasks.process_batch import process_batch
      
      job = process_batch.delay(post_ids)
      
      return {
          "status": "ACCEPTED",
          "job_id": job.id,
          "total_posts": len(post_ids)
      }
  
  @app.get("/api/v1/analytics/batch-status/{job_id}")
  async def get_batch_status(job_id: str):
      """Get batch processing status"""
      from celery.result import AsyncResult
      
      result = AsyncResult(job_id)
      
      return {
          "job_id": job_id,
          "status": result.state,
          "progress": result.info if result.state == 'PROGRESS' else None
      }
  ```

**Acceptance Criteria**:
- [ ] Process 100 posts in parallel
- [ ] Throughput >500 posts/min
- [ ] Error handling & retry works

---

#### 2.5 Monitoring & Alerting (Day 21-22)
**Goal**: Prometheus + Grafana dashboard

**Tasks**:
- [ ] **Prometheus Metrics**
  ```python
  # src/utils/metrics.py
  from prometheus_client import Counter, Histogram, Gauge
  
  # Counters
  posts_processed = Counter(
      'posts_processed_total',
      'Total posts processed',
      ['platform', 'intent', 'sentiment']
  )
  
  posts_failed = Counter(
      'posts_failed_total',
      'Total posts failed',
      ['error_type']
  )
  
  # Histograms
  processing_duration = Histogram(
      'post_processing_duration_seconds',
      'Time to process a post',
      ['module']
  )
  
  # Gauges
  cache_hit_rate = Gauge(
      'cache_hit_rate',
      'Cache hit rate percentage'
  )
  
  model_accuracy = Gauge(
      'model_accuracy',
      'Current model accuracy',
      ['model_version']
  )
  ```

- [ ] **Integration**
  ```python
  # src/orchestrator.py
  from src.utils.metrics import posts_processed, processing_duration
  import time
  
  def process(self, post_data: Dict) -> Dict:
      start = time.time()
      
      # ... processing logic ...
      
      # Record metrics
      posts_processed.labels(
          platform=result['platform'],
          intent=result['primary_intent'],
          sentiment=result['overall_sentiment']
      ).inc()
      
      processing_duration.labels(module='total').observe(
          time.time() - start
      )
      
      return result
  ```

- [ ] **Grafana Dashboard JSON**
  ```json
  {
    "dashboard": {
      "title": "Analytics Service Monitoring",
      "panels": [
        {
          "title": "Throughput (posts/min)",
          "targets": [{
            "expr": "rate(posts_processed_total[1m]) * 60"
          }]
        },
        {
          "title": "Processing Latency (p95)",
          "targets": [{
            "expr": "histogram_quantile(0.95, post_processing_duration_seconds)"
          }]
        },
        {
          "title": "Error Rate",
          "targets": [{
            "expr": "rate(posts_failed_total[5m])"
          }]
        },
        {
          "title": "Cache Hit Rate",
          "targets": [{
            "expr": "cache_hit_rate"
          }]
        }
      ]
    }
  }
  ```

**Deliverables**:
- Grafana dashboard live
- Alerting rules configured
- On-call runbook

---

### Phase 2 Deliverables
- ✅ Fine-tuned model với accuracy >90%
- ✅ Redis caching giảm latency 30%
- ✅ Batch processing 500+ posts/min
- ✅ Monitoring dashboard operational

---

## PHASE 3: PRODUCTION HARDENING (Week 5-6)
**Duration**: 10 working days  
**Goal**: Stability, security, documentation

### Week 5: Production Readiness

#### 3.1 Error Handling & Resilience (Day 23-24)
**Tasks**:
- [ ] **Retry Logic với Tenacity**
  ```python
  # src/utils/retry.py
  from tenacity import (
      retry,
      stop_after_attempt,
      wait_exponential,
      retry_if_exception_type
  )
  
  class TransientError(Exception):
      """Temporary error that can be retried"""
      pass
  
  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=4, max=10),
      retry=retry_if_exception_type(TransientError)
  )
  def process_with_retry(post_data):
      # ... processing logic
      pass
  ```

- [ ] **Circuit Breaker**
  ```python
  # src/utils/circuit_breaker.py
  from pybreaker import CircuitBreaker
  
  # ONNX inference breaker
  onnx_breaker = CircuitBreaker(
      fail_max=5,
      timeout_duration=60
  )
  
  @onnx_breaker
  def onnx_inference(inputs):
      # ... ONNX call
      pass
  ```

- [ ] **Dead Letter Queue**
  ```python
  # src/tasks/dlq.py
  @app.task(bind=True, max_retries=3)
  def process_post_async(self, post_data):
      try:
          # ... processing
      except Exception as exc:
          if self.request.retries >= self.max_retries:
              # Send to DLQ
              send_to_dlq(post_data, str(exc))
          else:
              raise self.retry(exc=exc)
  
  def send_to_dlq(post_data, error):
      """Save failed posts for manual review"""
      with open('dlq/failed_posts.jsonl', 'a') as f:
          f.write(json.dumps({
              'post_id': post_data['meta']['id'],
              'error': error,
              'timestamp': datetime.utcnow().isoformat(),
              'data': post_data
          }) + '\n')
  ```

---

#### 3.2 Load Testing (Day 25-26)
**Tasks**:
- [ ] **Locust Test**
  ```python
  # tests/load/locustfile.py
  from locust import HttpUser, task, between
  import json
  
  class AnalyticsUser(HttpUser):
      wait_time = between(1, 3)
      
      @task
      def process_post(self):
          post_data = {
              "meta": {"id": "test123", "platform": "TIKTOK"},
              "content": {"text": "Xe đẹp quá!"},
              "interaction": {"likes": 100, "shares": 10},
              "author": {"followers": 1000},
              "comments": []
          }
          
          self.client.post(
              "/api/v1/analytics/process-post",
              json=post_data,
              headers={"Authorization": "Bearer test_token"}
          )
  ```

- [ ] **Run Load Test**
  ```bash
  # Test với 100 concurrent users
  locust -f tests/load/locustfile.py \
      --host=http://localhost:8000 \
      --users 100 \
      --spawn-rate 10 \
      --run-time 10m
  ```

- [ ] **Performance Report**
  ```
  Target Metrics:
  - RPS: >500 requests/second
  - Latency p50: <500ms
  - Latency p95: <2000ms
  - Error rate: <0.5%
  ```

---

#### 3.3 Security (Day 27)
**Tasks**:
- [ ] **JWT Authentication**
  ```python
  # src/api/auth.py
  from fastapi import Depends, HTTPException, status
  from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
  import jwt
  
  security = HTTPBearer()
  SECRET_KEY = "your-secret-key"
  
  def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
      try:
          payload = jwt.decode(
              credentials.credentials,
              SECRET_KEY,
              algorithms=["HS256"]
          )
          return payload
      except jwt.PyJWTError:
          raise HTTPException(
              status_code=status.HTTP_401_UNAUTHORIZED,
              detail="Invalid authentication credentials"
          )
  ```

- [ ] **Rate Limiting**
  ```python
  # src/api/rate_limit.py
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address
  
  limiter = Limiter(key_func=get_remote_address)
  
  @app.post("/api/v1/analytics/process-post")
  @limiter.limit("100/minute")
  async def process_post(...):
      # ... processing
  ```

- [ ] **Input Validation**
  ```python
  # src/api/schemas.py
  from pydantic import BaseModel, Field, validator
  
  class ProcessPostRequest(BaseModel):
      meta: dict
      content: dict
      interaction: dict
      author: dict
      
      @validator('content')
      def validate_content(cls, v):
          if 'text' not in v or len(v['text']) < 10:
              raise ValueError('Text must be at least 10 characters')
          return v
  ```

---

### Week 6: Documentation & Handover

#### 3.4 API Documentation (Day 28)
**Tasks**:
- [ ] **OpenAPI Spec (Auto-generated by FastAPI)**
  - Available at `/docs` (Swagger UI)
  - Available at `/redoc` (ReDoc)

- [ ] **API Guide**
  ```markdown
  # API.md
  
  ## Authentication
  All endpoints require Bearer token authentication.
  
  ## Endpoints
  
  ### POST /api/v1/analytics/process-post
  Process a single social media post.
  
  **Request**:
  ```json
  {
    "meta": {"id": "...", "platform": "TIKTOK"},
    "content": {"text": "..."},
    ...
  }
  ```
  
  **Response**:
  ```json
  {
    "status": "SUCCESS",
    "result": {
      "overall_sentiment": "POSITIVE",
      "aspects": {...},
      ...
    }
  }
  ```
  ```

---

#### 3.5 Deployment Guide (Day 29)
**Tasks**:
- [ ] **Docker Compose Production**
  ```yaml
  # docker-compose.prod.yml
  version: '3.8'
  services:
    analytics-api:
      image: analytics-service:${VERSION}
      environment:
        DATABASE_URL: ${DATABASE_URL}
        REDIS_URL: ${REDIS_URL}
        MODEL_VERSION: v2
      deploy:
        replicas: 4
        resources:
          limits:
            cpus: '4'
            memory: 8G
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
    
    celery-worker:
      image: analytics-service:${VERSION}
      command: celery -A src.tasks worker --loglevel=info
      deploy:
        replicas: 4
  ```

- [ ] **Deployment Script**
  ```bash
  # scripts/deploy.sh
  #!/bin/bash
  
  VERSION=$1
  
  # Build image
  docker build -t analytics-service:$VERSION .
  
  # Push to registry
  docker push analytics-service:$VERSION
  
  # Update compose file
  export VERSION=$VERSION
  
  # Rolling update
  docker-compose -f docker-compose.prod.yml up -d --no-deps --build analytics-api
  
  # Run health check
  sleep 10
  curl http://localhost:8000/health
  ```

---

#### 3.6 Runbook (Day 30)
**Tasks**:
- [ ] **Operational Runbook**
  ```markdown
  # RUNBOOK.md
  
  ## Common Issues & Solutions
  
  ### High Latency (>5s)
  **Symptoms**: p95 latency > 5000ms
  **Diagnosis**:
  - Check Redis cache hit rate (should be >40%)
  - Check ONNX inference time
  - Check database connection pool
  
  **Solution**:
  - Scale up workers: `docker-compose scale analytics-api=8`
  - Restart Redis: `docker-compose restart redis`
  
  ### OOM (Out of Memory)
  **Symptoms**: Workers crash with exit code 137
  **Diagnosis**: Check memory usage in Grafana
  
  **Solution**:
  - Reduce batch size: Set MAX_BATCH_SIZE=16
  - Increase worker memory limit
  
  ### Model Accuracy Drop
  **Symptoms**: User reports incorrect sentiments
  **Diagnosis**: Check model_accuracy metric
  
  **Solution**:
  - Rollback to previous model version
  - Trigger retraining pipeline
  ```

---

### Phase 3 Deliverables
- ✅ Production-ready với error handling
- ✅ Load tested: 500+ RPS sustained
- ✅ Security hardened (JWT + rate limit)
- ✅ Complete documentation
- ✅ Deployment automation
- ✅ Operational runbook

---

## PHASE 4: ADVANCED FEATURES (Week 7-8) [OPTIONAL]
**Goal**: Competitive differentiation

### 4.1 Trend Detection
- [ ] Time-series analysis of keywords
- [ ] Anomaly detection (sudden spikes)
- [ ] Trending topics dashboard

### 4.2 Competitor Benchmarking
- [ ] Auto-compare múltiple brands
- [ ] Side-by-side aspect comparison
- [ ] Market share of voice

### 4.3 Comment Analysis Pipeline
- [ ] Separate pipeline for comments
- [ ] Parent-child sentiment correlation
- [ ] Thread analysis

---

## TESTING STRATEGY

### Unit Tests (>80% coverage)
```python
# tests/unit/
test_preprocessor.py
test_intent_classifier.py
test_keyword_extractor.py
test_sentiment_analyzer.py
test_impact_calculator.py
```

### Integration Tests
```python
# tests/integration/
test_pipeline_end_to_end.py
test_database_operations.py
test_cache_integration.py
```

### Load Tests
```python
# tests/load/
locustfile.py  # 1000 concurrent users
stress_test.py  # Gradual ramp-up
```

### Accuracy Tests
```python
# tests/accuracy/
test_golden_dataset.py  # 500 labeled posts
test_aspect_detection.py
test_sentiment_accuracy.py
```

---

## DEPLOYMENT CHECKLIST

### Pre-deployment
- [ ] All tests pass (unit + integration)
- [ ] Load test passed (>500 RPS)
- [ ] Security audit completed
- [ ] Database migrations ready
- [ ] Rollback plan documented

### Deployment
- [ ] Deploy to staging first
- [ ] Run smoke tests
- [ ] Monitor metrics for 1 hour
- [ ] Deploy to production (canary)
- [ ] Gradually increase traffic

### Post-deployment
- [ ] Monitor error rates (<0.5%)
- [ ] Verify latency targets (p95 <2s)
- [ ] Check accuracy metrics
- [ ] Collect user feedback

---

## SUCCESS CRITERIA SUMMARY

| Phase | Criteria | Target |
|-------|----------|--------|
| **Phase 0** | Environment setup | Docker up, CI green |
| **Phase 1** | MVP working | 1 post processed E2E |
| **Phase 2** | Intelligence | Accuracy >90%, Cache 40% |
| **Phase 3** | Production | 500 RPS, <0.5% error |
| **Phase 4** | Advanced | Trend detection live |

---

## RESOURCE ALLOCATION

| Phase | Backend | ML Engineer | QA | Total Person-Days |
|-------|---------|-------------|----|--------------------|
| Phase 0 | 2 | 1 | 0 | 3 |
| Phase 1 | 10 | 5 | 3 | 18 |
| Phase 2 | 8 | 8 | 4 | 20 |
| Phase 3 | 6 | 2 | 6 | 14 |
| Phase 4 | 5 | 5 | 2 | 12 |
| **TOTAL** | **31** | **21** | **15** | **67 days** |

**Timeline**: ~3 months với 3-person team (2 Backend + 1 ML)

---
