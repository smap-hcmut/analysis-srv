## ADDED Requirements

### Requirement: Sentiment Model Semantic Correctness

The Analytics Engine SHALL ensure that the underlying sentiment model used by the ABSA pipeline
produces semantically correct labels for clearly positive and negative Vietnamese texts.

**Rationale**: Even with a correct architecture, an improperly configured or incompatible model
(e.g., wrong base model or missing special tokens) can yield consistently wrong sentiment
predictions. This requirement makes semantic correctness an explicit contract, not just
structural validity.

#### Scenario: Detect negative price sentiment

**Given** the text "Xe thiết kế rất đẹp nhưng giá quá đắt"  
**And** keywords mapped as:
- "thiết kế" → aspect="DESIGN"  
- "giá" → aspect="PRICE"

**When** running the ABSA pipeline end-to-end  
**Then** the system SHALL:
- Assign a POSITIVE sentiment label to DESIGN aspect with a score > 0  
- Assign a NEGATIVE sentiment label to PRICE aspect with a score < 0

#### Scenario: Detect overall negative sentiment

**Given** one of the following texts:
- "Sản phẩm dở tệ"  
- "Chất lượng kém"  
- "Rất tệ, không nên mua"  

**When** analyzing overall sentiment (without aspect keywords)  
**Then** the system SHALL:
- Assign overall label NEGATIVE (or VERY_NEGATIVE for 5-class models)  
- Return an overall score < 0

#### Scenario: Distinguish positive and negative aspects in mixed text

**Given** the text "Thiết kế rất đẹp nhưng pin yếu và giá cao"  
**And** keywords mapped as:
- "thiết kế" → aspect="DESIGN"  
- "pin" → aspect="PERFORMANCE"  
- "giá" → aspect="PRICE"  

**When** running aspect-based sentiment analysis  
**Then** the system SHALL:
- Assign a POSITIVE sentiment label to DESIGN aspect with a positive score  
- Assign NEGATIVE sentiment labels to both PERFORMANCE (pin) and PRICE aspects with negative scores

