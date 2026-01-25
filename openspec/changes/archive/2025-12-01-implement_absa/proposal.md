# Proposal: Implement Aspect-Based Sentiment Analyzer (ABSA)

**Change ID**: `implement_absa`  
**Status**: Draft  
**Date**: 2025-12-01  
**Author**: AI Assistant

## Summary

Implement Module 4: Aspect-Based Sentiment Analyzer (ABSA) that uses PhoBERT ONNX model with Context Windowing technique to provide both overall sentiment and aspect-level sentiment analysis for Vietnamese social media posts.

## Why

Currently, the analytics pipeline extracts keywords with aspect labels (DESIGN, PERFORMANCE, PRICE, SERVICE) but cannot determine sentiment for each aspect. Business users need actionable insights like "Customers like DESIGN but complain about PRICE" to make data-driven decisions. Without aspect-based sentiment, the system can only provide overall sentiment, which is insufficient for understanding what specific aspects drive customer satisfaction or dissatisfaction.

This change enables:
- **Granular Insights**: Understand sentiment per business aspect (not just overall)
- **Actionable Intelligence**: Identify which aspects need improvement (e.g., PRICE complaints)
- **Business Value**: Enable aspect-level decision making (e.g., "Focus marketing on DESIGN strengths")

## Context

### Current State
- ✅ **Phase 0**: Foundation, PhoBERT ONNX integration, SpaCy-YAKE integration completed
- ✅ **Module 1**: TextPreprocessor - merges and normalizes content
- ✅ **Module 2**: IntentClassifier - filters noise and classifies intent
- ✅ **Module 3**: KeywordExtractor - extracts aspect-aware keywords (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)
- ⏳ **Module 4**: SentimentAnalyzer - **PENDING** (this proposal)
- ⏳ **Module 5**: ImpactCalculator - PENDING (depends on Module 4)

### Problem Statement

The analytics pipeline currently extracts keywords with aspect labels but cannot determine sentiment for each aspect. For example:
- Text: "Xe thiết kế đẹp nhưng giá quá đắt"
- Keywords extracted: ["thiết kế" (DESIGN), "giá" (PRICE)]
- **Missing**: Sentiment for DESIGN (POSITIVE) and PRICE (NEGATIVE)

Without aspect-based sentiment, business users cannot answer questions like:
- "What do customers like about our product?" (DESIGN: POSITIVE)
- "What are the main complaints?" (PRICE: NEGATIVE, PERFORMANCE: NEGATIVE)

### Solution Overview

Implement `SentimentAnalyzer` that:
1. **Overall Sentiment**: Uses PhoBERT ONNX to analyze full text
2. **Aspect-Based Sentiment**: Uses Context Windowing technique to analyze sentiment around each keyword
3. **Weighted Aggregation**: Combines multiple mentions of same aspect into single sentiment score
4. **Smart Context Extraction**: Extracts meaningful context windows (boundary snapping to avoid cutting words)

## Goals

1. **Primary Goal**: Enable aspect-level sentiment analysis for actionable business insights
2. **Performance Goal**: Maintain <100ms inference time per post (using existing PhoBERT ONNX)
3. **Integration Goal**: Seamlessly integrate with Module 3 (KeywordExtractor) output
4. **Quality Goal**: Provide accurate sentiment scores with confidence metrics

## Scope

### In Scope
- ✅ Implement `SentimentAnalyzer` class in `services/analytics/sentiment/sentiment_analyzer.py`
- ✅ Context Windowing algorithm (smart boundary snapping)
- ✅ Weighted aggregation for multiple aspect mentions
- ✅ Integration with existing `PhoBERTONNX` infrastructure
- ✅ Unit tests, integration tests, performance benchmarks
- ✅ Configuration management (window size, thresholds)

### Out of Scope
- ❌ Model fine-tuning (uses existing PhoBERT ONNX)
- ❌ New model training
- ❌ Module 5 (ImpactCalculator) - separate proposal
- ❌ API endpoints (will be added in orchestrator phase)

## Technical Approach

### Architecture

```
TextPreprocessor → IntentClassifier → KeywordExtractor → SentimentAnalyzer
                                                              │
                                                              ├─ Overall Sentiment (full text)
                                                              └─ Aspect Sentiment (context windows)
```

### Key Components

1. **SentimentAnalyzer Class**
   - Main entry point: `analyze(text, keywords)`
   - Returns: `{overall: {...}, aspects: {DESIGN: {...}, PRICE: {...}}}`
   - Uses `PhoBERTONNX` from `infrastructure/ai/phobert_onnx.py`

2. **Context Windowing**
   - Extract ±N characters around keyword
   - Smart boundary snapping (expand to nearest whitespace/punctuation)
   - Prevents cutting words mid-sentence

3. **Weighted Aggregation**
   - Formula: `Score_final = Σ(Score_i × Confidence_i) / Σ(Confidence_i)`
   - Handles multiple mentions of same aspect
   - Maps aggregated score to label (POSITIVE/NEGATIVE/NEUTRAL)

4. **Configuration**
   - `CONTEXT_WINDOW_SIZE`: Default 60 characters
   - `THRESHOLD_POSITIVE`: Default 0.25
   - `THRESHOLD_NEGATIVE`: Default -0.25

### Integration Points

- **Input**: 
  - `text`: Clean text from TextPreprocessor
  - `keywords`: List from KeywordExtractor with `{keyword, aspect, position, ...}`
- **Output**: 
  - Overall sentiment (label, score, confidence, probabilities)
  - Aspect sentiments (per aspect: label, score, confidence, mentions_count, keywords)

### Dependencies

- ✅ `infrastructure/ai/phobert_onnx.py` - PhoBERT ONNX wrapper (already available)
- ✅ `services/analytics/keyword/keyword_extractor.py` - Keyword extraction with aspects
- ✅ `core/config.py` - Configuration management

## Success Criteria

1. ✅ All unit tests pass (coverage >90%)
2. ✅ Integration tests pass with real PhoBERT model
3. ✅ Performance: <100ms per post (including aspect analysis)
4. ✅ Accuracy: Aspect sentiment matches manual labeling on test set (>85%)
5. ✅ Handles edge cases: empty keywords, missing context, multiple mentions

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Context window too small/large | Medium | Medium | Make window size configurable, test with various sizes |
| Aggregation loses nuance | Low | Medium | Use weighted average with confidence, preserve mention count |
| PhoBERT accuracy on short contexts | Medium | High | Test with real data, fallback to overall sentiment if context too short |
| Performance degradation | Low | Medium | Cache context extraction, batch processing if needed |

## References

- `documents/phase_4_proposal.md` - Detailed algorithm specification
- `documents/master-proposal.md` - Overall architecture (Section 4.4)
- `documents/implement_plan.md` - Implementation roadmap (Module 4)
- `infrastructure/ai/phobert_onnx.py` - Existing PhoBERT ONNX wrapper

## Next Steps

1. Review and approve this proposal
2. Create spec deltas in `specs/aspect_based_sentiment/spec.md`
3. Implement according to `tasks.md`
4. Test and validate against success criteria
5. Integrate with orchestrator (future phase)

