# Topic Definition Quick Guide

## Topic Structure

```json
{
    "topic_key": {
        "name": "Human-readable name",
        "description": "Detailed description for embeddings",
        "keywords": ["keyword1", "keyword2", ...],
        "category": "optional_grouping"
    }
}
```

---

## Field Explanations

### 1. `name` (Required)
**What**: Human-readable display name  
**Used for**: Dashboards, reports, UI displays  
**Example**: `"Fuel Pricing"` (not `"fuel_pricing"`)  
**Tip**: Clear, title case, no abbreviations

### 2. `description` (Required)
**What**: Detailed description of the topic  
**Used for**: Generating embedding vector (1536-dim) for similarity matching  
**Why critical**: Better description = better classification accuracy  
**Should include**: What it covers, context, key concepts, examples  
**Length**: 50-200 words recommended  

**Example:**
```json
"description": "Fuel pricing policies, subsidies, and pump price changes affecting petroleum products in Nigeria. Includes discussions about petrol, diesel, gasoline pricing, fuel subsidy removal, pump price adjustments, and economic impact of fuel pricing decisions by government and NNPC."
```

### 3. `keywords` (Required)
**What**: Array of relevant keywords/phrases  
**Used for**: Fast keyword matching (fallback + confidence boosting)  
**How it works**: Counts keyword matches in mention text  
**Should include**: Main terms, variations, synonyms, related terms  
**Count**: 5-15 keywords recommended  

**Example:**
```json
"keywords": ["fuel", "petrol", "diesel", "subsidy", "pump price", "pricing", "gasoline", "pms", "pms price"]
```

### 4. `category` (Optional)
**What**: High-level grouping for organization  
**Used for**: Filtering, analytics, admin organization  
**Common values**: `"energy"`, `"education"`, `"security"`, `"economy"`, `"health"`, `"executive"`  
**Tip**: Use consistently across related topics

---

## How Classification Works

1. **Keyword Matching**: Count keywords in mention → keyword score (0.0-1.0)
2. **Embedding Similarity**: Compare mention embedding to topic embedding (from description) → similarity score (0.0-1.0)
3. **Combined Score**: `(0.3 × keyword_score) + (0.7 × embedding_score)`
4. **Result**: Topics above threshold (e.g., 0.5) are assigned

---

## Complete Example

```json
{
    "fuel_pricing": {
        "name": "Fuel Pricing",
        "description": "Fuel pricing policies, subsidies, and pump price changes affecting petroleum products in Nigeria. Includes discussions about petrol, diesel, gasoline pricing, fuel subsidy removal or implementation, pump price adjustments, and economic impact of fuel pricing decisions by the government and NNPC.",
        "keywords": ["fuel", "petrol", "diesel", "subsidy", "pump price", "pricing", "gasoline", "pms", "pms price", "refinery"],
        "category": "energy"
    }
}
```

---

## Quick Tips

✅ **DO**:  
- Write detailed, context-rich descriptions
- Include keyword variations and synonyms
- Use clear, human-readable names

❌ **DON'T**:  
- Use vague or too-short descriptions
- Use only one keyword
- Use technical slugs as names

---

*One-Page Quick Reference*

