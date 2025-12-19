# Intent Classification Capability

**Capability**: `intent_classification`  
**Owner**: Analytics Engine Team  
**Status**: Proposed

---

## ADDED Requirements

### Requirement: Intent Pattern Matching

The Analytics Engine SHALL classify social media posts into intent categories using regex-based pattern matching.

**Rationale**: Social media posts have different intents (buying, complaining, spamming). Classifying intent early allows the system to filter noise (SPAM/SEEDING) before expensive AI processing and prioritize critical posts (CRISIS) for immediate attention.

#### Scenario: Classify CRISIS Intent

**Given** a post with text "VinFast lừa đảo khách hàng, tẩy chay ngay"  
**When** the intent classifier processes the text  
**Then** intent SHALL be "CRISIS"  
**And** confidence SHALL be >= 0.9  
**And** should_skip SHALL be False  
**And** matched_pattern SHALL contain the crisis pattern

#### Scenario: Classify SEEDING Intent

**Given** a post with text "Bán xe VinFast giá rẻ, liên hệ 0912345678"  
**When** the intent classifier processes the text  
**Then** intent SHALL be "SEEDING"  
**And** should_skip SHALL be True  
**And** matched_pattern SHALL contain phone number pattern

#### Scenario: Classify SPAM Intent

**Given** a post with text "Vay tiền nhanh, lãi suất thấp"  
**When** the intent classifier processes the text  
**Then** intent SHALL be "SPAM"  
**And** should_skip SHALL be True

#### Scenario: Classify COMPLAINT Intent

**Given** a post with text "Xe lỗi không sửa được, thất vọng quá"  
**When** the intent classifier processes the text  
**Then** intent SHALL be "COMPLAINT"  
**And** should_skip SHALL be False  
**And** confidence SHALL be >= 0.9

#### Scenario: Classify LEAD Intent

**Given** a post with text "Giá xe VinFast VF5 bao nhiêu? Mua ở đâu?"  
**When** the intent classifier processes the text  
**Then** intent SHALL be "LEAD"  
**And** should_skip SHALL be False

#### Scenario: Classify SUPPORT Intent

**Given** a post with text "Cách sạc xe điện như thế nào? Showroom ở đâu?"  
**When** the intent classifier processes the text  
**Then** intent SHALL be "SUPPORT"  
**And** should_skip SHALL be False

#### Scenario: Default to DISCUSSION Intent

**Given** a post with text "Xe đẹp quá"  
**When** the intent classifier processes the text  
**And** no patterns match  
**Then** intent SHALL be "DISCUSSION"  
**And** confidence SHALL be 0.5  
**And** should_skip SHALL be False

---

### Requirement: Priority-Based Conflict Resolution

The Analytics Engine SHALL resolve conflicts when multiple intent patterns match by selecting the highest priority intent.

**Rationale**: A post can match multiple patterns (e.g., "Giá xe này lừa đảo" matches both LEAD and CRISIS). The system must prioritize CRISIS over LEAD to ensure critical posts are not missed.

#### Scenario: CRISIS Overrides LEAD

**Given** a post with text "Giá xe này lừa đảo khách hàng"  
**When** the intent classifier processes the text  
**And** both CRISIS and LEAD patterns match  
**Then** intent SHALL be "CRISIS"  
**And** priority SHALL be 10 (highest)  
**And** LEAD pattern SHALL be ignored

#### Scenario: SEEDING Overrides COMPLAINT

**Given** a post with text "Xe lỗi quá, liên hệ 0912345678 để mua xe khác"  
**When** the intent classifier processes the text  
**And** both SEEDING and COMPLAINT patterns match  
**Then** intent SHALL be "SEEDING"  
**And** should_skip SHALL be True

#### Scenario: Priority Order Validation

**Given** the intent priority mapping  
**When** validating priority values  
**Then** CRISIS SHALL have priority 10  
**And** SEEDING SHALL have priority 9  
**And** SPAM SHALL have priority 9  
**And** COMPLAINT SHALL have priority 7  
**And** LEAD SHALL have priority 5  
**And** SUPPORT SHALL have priority 4  
**And** DISCUSSION SHALL have priority 1

---

### Requirement: Vietnamese Language Support

The Analytics Engine SHALL support Vietnamese-specific patterns for intent classification.

**Rationale**: Vietnamese social media uses unique expressions and slang that differ from English. Patterns must be optimized for Vietnamese text to achieve high accuracy.

#### Scenario: Vietnamese Crisis Keywords

**Given** Vietnamese crisis keywords ["tẩy chay", "lừa đảo", "scam", "phốt", "bóc phốt"]  
**When** a post contains any of these keywords  
**Then** intent SHALL be classified as "CRISIS"

#### Scenario: Vietnamese Phone Number Pattern

**Given** a post with Vietnamese phone number "0912345678"  
**When** the pattern matches 9-11 digit sequences  
**Then** intent SHALL be classified as "SEEDING"

#### Scenario: Vietnamese Complaint Expressions

**Given** Vietnamese complaint expressions ["thất vọng", "tệ quá", "đừng mua", "phí tiền"]  
**When** a post contains any of these expressions  
**Then** intent SHALL be classified as "COMPLAINT"

#### Scenario: Case Insensitive Matching

**Given** a post with text "LỪA ĐẢO" (uppercase)  
**When** the intent classifier processes the text  
**Then** intent SHALL be "CRISIS"  
**And** pattern matching SHALL be case-insensitive

---

### Requirement: Skip Logic for Noise Filtering

The Analytics Engine SHALL provide a skip flag to indicate when posts should bypass expensive AI processing.

**Rationale**: SPAM and SEEDING posts waste compute resources on PhoBERT/SpaCy inference (~50ms each). Early filtering can save 30-40% of processing costs.

#### Scenario: Skip SPAM Posts

**Given** a post classified as "SPAM"  
**When** the orchestrator checks should_skip flag  
**Then** should_skip SHALL be True  
**And** PhoBERT sentiment analysis SHALL be skipped  
**And** post SHALL be saved with NEUTRAL sentiment

#### Scenario: Skip SEEDING Posts

**Given** a post classified as "SEEDING"  
**When** the orchestrator checks should_skip flag  
**Then** should_skip SHALL be True  
**And** keyword extraction SHALL be skipped

#### Scenario: Process Valid Intents

**Given** a post classified as "COMPLAINT", "LEAD", "SUPPORT", or "DISCUSSION"  
**When** the orchestrator checks should_skip flag  
**Then** should_skip SHALL be False  
**And** full AI pipeline SHALL be executed

#### Scenario: Always Process CRISIS

**Given** a post classified as "CRISIS"  
**When** the orchestrator checks should_skip flag  
**Then** should_skip SHALL be False  
**And** full AI pipeline SHALL be executed  
**And** alert SHALL be triggered

---

### Requirement: Performance Optimization

The Analytics Engine SHALL process intent classification in under 1 millisecond per post.

**Rationale**: Intent classification is a gatekeeper that runs before all AI models. It must be extremely fast to avoid becoming a bottleneck.

#### Scenario: Pre-compiled Regex Patterns

**Given** the IntentClassifier is initialized  
**When** patterns are loaded  
**Then** all regex patterns SHALL be pre-compiled  
**And** patterns SHALL NOT be recompiled on each predict() call

#### Scenario: Single Text Processing Speed

**Given** a typical post with 100 characters  
**When** intent classification is performed  
**Then** processing time SHALL be < 1 millisecond

#### Scenario: Batch Processing Efficiency

**Given** a batch of 100 posts  
**When** intent classification is performed on all posts  
**Then** average processing time per post SHALL be < 1 millisecond

---

### Requirement: Output Contract

The Analytics Engine SHALL return a standardized intent classification result.

**Rationale**: Downstream modules (Orchestrator, Dashboard) need consistent output format to make decisions and display results.

#### Scenario: Complete Output Structure

**Given** any post is classified  
**When** the predict() method returns  
**Then** output SHALL contain "intent" field  
**And** output SHALL contain "confidence" field  
**And** output SHALL contain "should_skip" field  
**And** output SHALL contain "matched_pattern" field (optional)

#### Scenario: Confidence Values

**Given** a post matches a regex pattern  
**When** intent is classified  
**Then** confidence SHALL be 0.9 for rule-based matches  
**And** confidence SHALL be 0.5 for default DISCUSSION

#### Scenario: Matched Pattern Tracking

**Given** a post matches "lỗi.*không.*sửa" pattern  
**When** intent is classified as COMPLAINT  
**Then** matched_pattern SHALL be "lỗi.*không.*sửa"  
**And** matched_pattern SHALL be included in output for debugging
