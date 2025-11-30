## MODIFIED Requirements

### Requirement: Text Normalization

The Analytics Engine SHALL normalize text by removing noise and standardizing format for AI processing, including handling Vietnamese slang and special Unicode fonts.

**Rationale**: Raw social media text contains URLs, emojis, inconsistent formatting, Vietnamese slang (teencode), and special Unicode fonts that can confuse AI models. Normalization ensures clean, consistent input optimized for PhoBERT sentiment analysis.

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
**Then** text SHALL be converted to NFKC form (Compatibility Decomposition)  
**And** diacritics SHALL be preserved correctly  
**And** special Unicode fonts (e.g., Mathematical Alphanumeric Symbols) SHALL be converted to standard characters  
**And** text SHALL be lowercase

#### Scenario: Normalize Vietnamese Slang

**Given** Vietnamese text containing slang abbreviations "ko uổng tiền vkl ae ơi"  
**When** the preprocessor normalizes the text  
**Then** slang terms SHALL be replaced with formal equivalents  
**And** "ko" SHALL become "không"  
**And** "vkl" SHALL become "rất"  
**And** "ae" SHALL become "anh em"  
**And** replacements SHALL use word boundaries to avoid false matches

#### Scenario: Normalize Whitespace

**Given** text with multiple spaces and newlines  
**When** the preprocessor normalizes the text  
**Then** multiple spaces SHALL be collapsed to single space  
**And** leading/trailing whitespace SHALL be removed

---

## MODIFIED Requirements

### Requirement: Content Merging

The Analytics Engine SHALL merge content from multiple sources (caption, transcription, comments) into a unified text input for AI processing, with clean separation between sections.

**Rationale**: Social media posts contain information across multiple fields. Video transcriptions (STT output) often contain the most detailed content, while comments provide user reactions. Merging these sources provides richer context for AI models. Clean separation prevents artifacts that confuse tokenizers.

#### Scenario: Merge with All Sources

**Given** a post with caption, transcription, and comments  
**When** the preprocessor merges content  
**Then** transcription SHALL appear first (highest priority)  
**And** caption SHALL appear second  
**And** top N comments (sorted by likes) SHALL appear last  
**And** sections SHALL be separated by period and space  
**And** each part SHALL be stripped of leading/trailing whitespace and trailing punctuation before joining  
**And** duplicate periods SHALL be removed (e.g., `..` → `.`)

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

## MODIFIED Requirements

### Requirement: Noise Statistics

The Analytics Engine SHALL calculate statistics to identify spam and low-quality posts, including detection of phone numbers and spam keywords.

**Rationale**: Not all posts are worth processing with expensive AI models. Statistics help the orchestrator filter out noise (spam, emoji-only posts, too short posts, loan advertisements) before AI inference. Enhanced spam signals beyond hashtag ratio improve detection of sophisticated spam patterns.

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

#### Scenario: Detect Phone Numbers

**Given** text containing Vietnamese phone number patterns (e.g., "0912345678", "0387654321")  
**When** statistics are calculated  
**Then** has_phone SHALL be True  
**And** this indicates potential spam or advertisement

#### Scenario: Detect Spam Keywords

**Given** text containing spam keywords (e.g., "vay vốn", "lãi suất", "giải ngân", "bán sim", "tuyển dụng")  
**When** statistics are calculated  
**Then** has_spam_keyword SHALL be True  
**And** this indicates potential spam or advertisement  
**And** orchestrator can combine with other signals for filtering

---

## ADDED Requirements

### Requirement: Teencode Normalization

The Analytics Engine SHALL normalize Vietnamese slang and abbreviations (teencode) to formal Vietnamese equivalents to improve AI model accuracy.

**Rationale**: PhoBERT and other Vietnamese NLP models are trained on formal Vietnamese text (news, articles). Social media posts often contain slang abbreviations (e.g., `ko` = `không`, `vkl` = `rất`). Normalizing these terms improves sentiment analysis accuracy.

#### Scenario: Replace Common Slang Terms

**Given** text containing "ko uổng tiền mua vkl ae ơi"  
**When** the preprocessor normalizes the text  
**Then** "ko" SHALL be replaced with "không"  
**And** "vkl" SHALL be replaced with "rất"  
**And** "ae" SHALL be replaced with "anh em"  
**And** result SHALL be "không uổng tiền mua rất anh em ơi"

#### Scenario: Use Word Boundaries

**Given** text containing "kaka" (not slang)  
**When** the preprocessor normalizes the text  
**Then** "k" SHALL NOT be replaced with "không"  
**And** word boundaries SHALL prevent false matches

#### Scenario: Preserve Sentiment Intensity

**Given** text containing "vkl" or "vcl" (very strong emotion)  
**When** the preprocessor normalizes the text  
**Then** slang SHALL be replaced with equivalent intensity word ("rất")  
**And** sentiment meaning SHALL be preserved

