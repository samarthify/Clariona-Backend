# Keyword Matching vs Embedding Matching
## How They Work and How They Differ

**Date**: January 27, 2025

---

## Overview

The TopicClassifier uses **two complementary approaches** to classify text:
1. **Keyword Matching** - Exact/substring matching of predefined keywords
2. **Embedding Matching** - Semantic similarity using vector embeddings

These are combined into a **hybrid classification system** that leverages the strengths of both approaches.

---

## 1. Keyword Matching

### How It Works

**Process:**
1. Text is converted to lowercase
2. Each keyword from the topic's keyword list is checked against the text
3. Matches are counted (with word boundary detection)
4. Score is calculated based on:
   - Proportion of keywords matched
   - Number of matches (logarithmic boost for multiple matches)
   - Word boundary matching (whole words get higher scores)

**Code Implementation:**
```python
def _keyword_match(self, text_lower: str, keywords: List[str]) -> float:
    # Count keyword matches
    matches = 0
    for keyword in keywords:
        keyword_lower = keyword.lower()
        # Check for word boundary matches (more precise)
        if keyword_lower in text_lower:
            # Boost if it's a whole word match
            if f" {keyword_lower} " in f" {text_lower} ":
                matches += 1.2  # Boost for whole word matches
            else:
                matches += 1.0
    
    # Base score: proportion of keywords matched
    base_score = min(matches / len(keywords), 1.0)
    
    # Boost score if multiple matches
    if matches > 1:
        boost = 1 + (np.log(matches + 1) / 8)
        base_score = min(base_score * boost, 1.0)
    
    return min(base_score, 1.0)
```

### Characteristics

**✅ Strengths:**
- **Fast**: Simple string matching, very quick
- **Precise**: Exact matches when keywords are present
- **Interpretable**: Easy to see why something matched
- **No API calls**: Works offline, no external dependencies

**❌ Limitations:**
- **Exact match required**: "farmers" doesn't match "farming" keyword
- **No semantic understanding**: Can't understand synonyms or related concepts
- **Keyword list dependency**: Only matches if keywords are in the predefined list
- **Misspellings**: "presidnt" won't match "president"
- **Context blind**: "crisis" matches healthcare even if text is about faith crisis

**Example:**
```
Text: "The president announced new fuel pricing policies"
Keywords: ["president", "announced", "fuel", "pricing"]

Matches:
- "president" ✓ (in text)
- "announced" ✓ (in text)
- "fuel" ✓ (in text)
- "pricing" ✓ (in text)

Score: 4/4 = 1.0 (100% match)
```

---

## 2. Embedding Matching

### How It Works

**Process:**
1. Text is converted to a **1536-dimensional vector** using OpenAI's `text-embedding-3-small` model
2. Each topic has a **pre-computed embedding** (generated from topic name + description + keywords)
3. **Cosine similarity** is calculated between text embedding and topic embedding
4. Similarity score ranges from **-1 to 1** (typically 0 to 1 for normalized embeddings)
5. Score is normalized to **0-1 range** for consistency

**Code Implementation:**
```python
def cosine_similarity(vec1, vec2) -> float:
    # Calculate dot product
    dot_product = np.dot(vec1, vec2)
    
    # Calculate magnitudes
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    # Cosine similarity
    similarity = dot_product / (norm1 * norm2)
    
    # Clamp to [-1, 1]
    return float(np.clip(similarity, -1.0, 1.0))

# In classifier:
embedding_score = max(0.0, float(cosine_similarity(text_embedding, topic_embedding)))
```

### What Are Embeddings?

**Embeddings** are numerical representations of text that capture **semantic meaning**:
- Similar meanings → Similar vectors → High cosine similarity
- Different meanings → Different vectors → Low cosine similarity

**Example:**
- "fuel price increase" → Vector: [0.1, -0.3, 0.7, ...] (1536 numbers)
- "petrol cost hike" → Vector: [0.12, -0.28, 0.69, ...] (very similar!)
- "football match" → Vector: [-0.5, 0.2, -0.1, ...] (very different)

### Characteristics

**✅ Strengths:**
- **Semantic understanding**: Understands synonyms, related concepts, context
- **Flexible**: Works with variations, misspellings, informal language
- **Context aware**: Can understand meaning even if exact words aren't present
- **No keyword list needed**: Works based on meaning, not exact matches

**❌ Limitations:**
- **Requires embeddings**: Need to generate embeddings for text (API call or pre-computed)
- **Less interpretable**: Hard to see why something matched
- **Computational cost**: Vector operations are more expensive than string matching
- **Can be too broad**: May match related but not exact topics

**Example:**
```
Text: "The cost of living is rising, prices are going up everywhere"
Topic: "Inflation"

Keyword matching: 0.0 (no keywords like "inflation" or "price increase" in exact form)
Embedding matching: 0.58 (high similarity - understands "cost of living rising" = inflation)
```

---

## 3. How They're Combined

### Hybrid Scoring

The classifier combines both scores using **weighted average**:

```python
combined_score = (
    keyword_weight * keyword_score +      # Default: 40%
    embedding_weight * embedding_score    # Default: 60%
)
```

**Default Weights:**
- Keyword weight: **0.4** (40%)
- Embedding weight: **0.6** (60%)

### Boosting Logic

**1. Agreement Boost:**
If both keyword AND embedding agree (both have decent scores):
```python
if keyword_score > 0.15 and embedding_score > 0.25:
    combined_score = min(combined_score * 1.15, 1.0)  # +15% boost
```

**2. High Confidence Boost:**
If either score is very high:
```python
if keyword_score > 0.3 or embedding_score > 0.5:
    combined_score = min(combined_score * 1.05, 1.0)  # +5% boost
```

**3. Minimum Threshold:**
Skip if both are too low:
```python
if keyword_score == 0.0 and embedding_score < 0.25:
    continue  # Skip this topic
```

### Example Calculation

```
Text: "Dangote Refinery backs Tinubu govt's 15 per cent fuel import duty"

Topic: "Fuel Pricing"

Keyword Matching:
- "fuel" ✓ → matches
- "refinery" ✓ → matches
- Matches: 2/15 keywords = 0.133
- Boost for multiple matches: 1.1
- Final keyword_score: 0.184

Embedding Matching:
- Text embedding vs topic embedding
- Cosine similarity: 0.448
- Final embedding_score: 0.448

Combined Score:
- combined = 0.4 * 0.184 + 0.6 * 0.448 = 0.350
- Agreement boost: 0.15 < 0.15 (no boost)
- High confidence: 0.448 < 0.5 (no boost)
- Final confidence: 0.350

Result: Matches! (above threshold 0.2)
```

---

## 4. Key Differences

| Aspect | Keyword Matching | Embedding Matching |
|--------|-----------------|-------------------|
| **Method** | String/substring search | Vector similarity (cosine) |
| **Speed** | Very fast (~0.01ms) | Fast (~0.1ms) |
| **Understanding** | Literal/exact | Semantic/contextual |
| **Synonyms** | ❌ No | ✅ Yes |
| **Misspellings** | ❌ No | ✅ Yes |
| **Variations** | ❌ No | ✅ Yes |
| **Interpretability** | ✅ High (see exact matches) | ❌ Low (black box) |
| **Dependencies** | None | Requires embeddings |
| **API Calls** | None | Need OpenAI API (or pre-computed) |
| **False Positives** | Low (exact match) | Higher (semantic similarity) |
| **False Negatives** | High (misses variations) | Lower (catches variations) |

---

## 5. Real-World Examples

### Example 1: Exact Keyword Match

**Text:** "The president announced new fuel pricing policies"

**Keyword Matching:**
- "president" ✓
- "announced" ✓
- "fuel" ✓
- "pricing" ✓
- Score: **0.7** (high)

**Embedding Matching:**
- Semantic similarity: **0.45** (good)
- Score: **0.45**

**Combined:** 0.4 × 0.7 + 0.6 × 0.45 = **0.55** ✅

---

### Example 2: Semantic Match (No Keywords)

**Text:** "The cost of living is rising, everything is getting more expensive"

**Keyword Matching:**
- No exact keywords like "inflation" or "price increase"
- Score: **0.0** (no match)

**Embedding Matching:**
- Understands "cost of living rising" = inflation
- Semantic similarity: **0.58** (high)
- Score: **0.58**

**Combined:** 0.4 × 0.0 + 0.6 × 0.58 = **0.35** ✅

---

### Example 3: Both Fail

**Text:** "Nigeria is stacked with stars shining across Europe, AFCON season"

**Keyword Matching:**
- No topic keywords present
- Score: **0.0**

**Embedding Matching:**
- Sports content, not governance-related
- Semantic similarity: **0.15** (low)
- Score: **0.15**

**Combined:** 0.4 × 0.0 + 0.6 × 0.15 = **0.09**
**Result:** ❌ Below threshold (0.2), no match

---

### Example 4: False Positive (Keyword)

**Text:** "The Giant and Its Shadow: Nigeria's Crisis of Faith"

**Topic:** Healthcare Crisis

**Keyword Matching:**
- "crisis" ✓ (matches keyword)
- Score: **0.11** (low, but present)

**Embedding Matching:**
- Semantic similarity: **0.35** (moderate - "crisis" is related)
- Score: **0.35**

**Combined:** 0.4 × 0.11 + 0.6 × 0.35 = **0.25** ✅
**Result:** ⚠️ False positive - matched healthcare but text is about faith crisis

---

## 6. When to Use Each

### Use Keyword Matching When:
- ✅ You need **fast, exact matches**
- ✅ You have **comprehensive keyword lists**
- ✅ You want **interpretable results**
- ✅ You're working **offline** (no API access)
- ✅ You need **high precision** (exact matches only)

### Use Embedding Matching When:
- ✅ You need **semantic understanding**
- ✅ Text has **variations, synonyms, informal language**
- ✅ You want to catch **related concepts**
- ✅ You have **pre-computed embeddings**
- ✅ You need **broader coverage**

### Use Hybrid (Current Approach) When:
- ✅ You want **best of both worlds**
- ✅ You need **balanced precision and recall**
- ✅ You have **both keywords and embeddings**
- ✅ You want **robust classification**

---

## 7. Performance Comparison

Based on 100-record test:

| Metric | Keyword-Only | Embedding-Only | Hybrid |
|--------|--------------|----------------|--------|
| **Match Rate** | ~20% | ~40% | **54%** |
| **Speed** | ~0.01ms | ~0.1ms | ~0.48ms |
| **Precision** | High | Medium | **High** |
| **Recall** | Low | Medium | **High** |

**Conclusion:** Hybrid approach provides best overall performance.

---

## 8. Improving Each Method

### Improving Keyword Matching:
1. **Add more keywords** (especially informal/social media variations)
2. **Add stemming** (farmers → farming)
3. **Add partial matching** (presidential → president)
4. **Add context awareness** (crisis + healthcare context)

### Improving Embedding Matching:
1. **Better topic descriptions** (more detailed = better embeddings)
2. **Include keywords in embedding generation** (already done)
3. **Fine-tune thresholds** (adjust minimum similarity)
4. **Use better models** (text-embedding-3-large for better accuracy)

---

## Summary

**Keyword Matching:**
- Fast, exact, interpretable
- Misses variations and synonyms
- Requires comprehensive keyword lists

**Embedding Matching:**
- Semantic, flexible, catches variations
- Less interpretable, requires embeddings
- Can be too broad

**Hybrid Approach:**
- Combines strengths of both
- 54% match rate vs 20% keyword-only
- Best overall performance

The current system uses **40% keyword + 60% embedding** weighting, which provides a good balance between precision and recall.

---

*Documentation created: January 27, 2025*
















