# text_preprocessing Specification

## Purpose
TBD - created by archiving change implement_text_preprocessor. Update Purpose after archive.
## Requirements
### Requirement: Content Merging

The Analytics Engine SHALL merge content from multiple sources (caption, transcription, comments) into a unified text input for AI processing.

**Rationale**: Social media posts contain information across multiple fields. Video transcriptions (STT output) often contain the most detailed content, while comments provide user reactions. Merging these sources provides richer context for AI models.

#### Scenario: Merge with All Sources

**Given** a post with caption, transcription, and comments  
**When** the preprocessor merges content  
**Then** transcription SHALL appear first (highest priority)  
**And** caption SHALL appear second  
**And** top N comments (sorted by likes) SHALL appear last  
**And** sections SHALL be separated by period and space

#### Scenario: Merge with Transcription Only

**Given** a post with transcription but no caption or comments  
**When** the preprocessor merges content  
**Then** only transcription text SHALL be returned  
**And** no extra separators SHALL be added

#### Scenario: Merge with Comments Limit

**Given** a post with 20 comments  
**When** the preprocessor merges content with max_comments=5  
**Then** only the top 5 most-liked comments SHALL be included  
**And** comments SHALL be sorted by likes in descending order

#### Scenario: Handle Empty Inputs

**Given** a post with all empty/None fields  
**When** the preprocessor merges content  
**Then** an empty string SHALL be returned  
**And** no errors SHALL be raised

---

### Requirement: Text Normalization

The Analytics Engine SHALL normalize text by removing noise and standardizing format for AI processing.

**Rationale**: Raw social media text contains URLs, emojis, and inconsistent formatting that can confuse AI models. Normalization ensures clean, consistent input.

#### Scenario: Remove URLs

**Given** text containing "Check this out http://example.com and www.test.com"  
**When** the preprocessor normalizes the text  
**Then** URLs SHALL be removed  
**And** result SHALL be "check this out and"

#### Scenario: Remove Emojis

**Given** text containing "Great product 😍🔥👍"  
**When** the preprocessor normalizes the text  
**Then** emojis SHALL be removed  
**And** result SHALL be "great product"

#### Scenario: Process Hashtags

**Given** text containing "#VinFast #ElectricCar review"  
**When** the preprocessor normalizes the text  
**Then** hashtag symbols SHALL be removed  
**And** words SHALL be preserved  
**And** result SHALL be "vinfast electriccar review"

#### Scenario: Normalize Vietnamese Text

**Given** Vietnamese text with composed Unicode characters  
**When** the preprocessor normalizes the text  
**Then** text SHALL be converted to NFC form  
**And** diacritics SHALL be preserved correctly  
**And** text SHALL be lowercase

#### Scenario: Normalize Whitespace

**Given** text with multiple spaces and newlines  
**When** the preprocessor normalizes the text  
**Then** multiple spaces SHALL be collapsed to single space  
**And** leading/trailing whitespace SHALL be removed

---

### Requirement: Noise Statistics

The Analytics Engine SHALL calculate statistics to identify spam and low-quality posts.

**Rationale**: Not all posts are worth processing with expensive AI models. Statistics help the orchestrator filter out noise (spam, emoji-only posts, too short posts) before AI inference.

#### Scenario: Calculate Text Length

**Given** normalized text  
**When** statistics are calculated  
**Then** total_length SHALL be the character count  
**And** is_too_short SHALL be True if length < 10 characters

#### Scenario: Calculate Hashtag Ratio

**Given** text with hashtags  
**When** statistics are calculated  
**Then** hashtag_ratio SHALL be (hashtag_count / word_count)  
**And** ratio SHALL be between 0 and 1  
**And** high ratio (>0.5) indicates spam

#### Scenario: Calculate Reduction Ratio

**Given** original and normalized text  
**When** statistics are calculated  
**Then** reduction_ratio SHALL be (1 - clean_length / original_length)  
**And** high ratio indicates lots of noise removed

#### Scenario: Detect Transcription Presence

**Given** a post with transcription field  
**When** statistics are calculated  
**Then** has_transcription SHALL be True  
**And** this indicates video content is available

---

### Requirement: Source Breakdown

The Analytics Engine SHALL track the origin of text content for debugging and analysis.

**Rationale**: Understanding where text comes from (caption vs transcription vs comments) helps debug issues and analyze content quality.

#### Scenario: Track Source Lengths

**Given** a post with caption, transcription, and comments  
**When** preprocessing is performed  
**Then** source_breakdown SHALL include caption_len  
**And** source_breakdown SHALL include transcript_len  
**And** source_breakdown SHALL include comments_len  
**And** lengths SHALL be measured before merging

#### Scenario: Identify Primary Source

**Given** source breakdown data  
**When** analyzing the breakdown  
**Then** the largest length indicates the primary content source  
**And** this helps understand content type (video vs text post)

---

### Requirement: Full Preprocessing Pipeline

The Analytics Engine SHALL provide a complete preprocessing pipeline that combines all operations.

**Rationale**: Callers need a single method to perform all preprocessing steps in the correct order.

#### Scenario: Process Complete Post

**Given** a post with all content fields  
**When** the preprocess() method is called  
**Then** content SHALL be merged in priority order  
**And** text SHALL be normalized  
**And** statistics SHALL be calculated  
**And** source breakdown SHALL be provided  
**And** a PreprocessingResult SHALL be returned

#### Scenario: Handle Missing Fields

**Given** a post with some missing fields  
**When** the preprocess() method is called  
**Then** missing fields SHALL be treated as empty  
**And** no errors SHALL be raised  
**And** processing SHALL continue with available data

#### Scenario: Performance Requirement

**Given** a typical post (500 characters)  
**When** the preprocess() method is called  
**Then** processing SHALL complete in < 10 milliseconds  
**And** memory usage SHALL be minimal (no large intermediate objects)

