# Topic Definition Guide
## Understanding Each Field in Master Topics Configuration

---

## Topic Structure Overview

Each topic in `master_topics.json` has 4 main fields:

```json
{
    "topic_key": {
        "name": "...",
        "description": "...",
        "keywords": [...],
        "category": "..."
    }
}
```

---

## 1. `name` Field

### Purpose
Human-readable display name for the topic. Used in:
- Dashboard displays
- Reports
- User-facing interfaces
- Logs and debugging

### Characteristics
- **Short and clear**: Easy to understand at a glance
- **Title case**: Proper capitalization
- **No abbreviations**: Full words preferred (unless commonly understood)

### Examples

✅ **Good Examples:**
```json
"name": "Fuel Pricing"
"name": "Presidential Announcements"
"name": "Military Operations"
"name": "Education Funding"
```

❌ **Bad Examples:**
```json
"name": "fuel_pricing"  // Too technical, use display name
"name": "Pres. Ann."    // Abbreviation unclear
"name": "mil ops"       // Too abbreviated
```

### Real Example
```json
{
    "fuel_pricing": {
        "name": "Fuel Pricing",
        ...
    }
}
```

**Why it matters**: When a mention is classified into `fuel_pricing`, users see "Fuel Pricing" in dashboards and reports.

---

## 2. `description` Field

### Purpose
**Detailed description used for embedding generation**. This is critical because:
- The description is converted to an embedding vector
- Embedding similarity is used to match mentions to topics
- Better descriptions = better classification accuracy

### Characteristics
- **Comprehensive**: Should describe what the topic covers
- **Context-rich**: Include relevant context (e.g., "in Nigeria", "government policy")
- **Specific**: Mention key concepts, entities, or actions
- **50-200 words**: Long enough to be meaningful, not too long

### How It's Used
1. **Embedding Generation**: Description text → 1536-dim embedding vector
2. **Similarity Matching**: Mention embedding compared to topic embedding
3. **Classification**: Higher similarity = higher confidence for that topic

### Examples

✅ **Good Example:**
```json
{
    "fuel_pricing": {
        "description": "Fuel pricing policies, subsidies, and pump price changes affecting petroleum products in Nigeria. Includes discussions about petrol, diesel, gasoline pricing, fuel subsidy removal or implementation, pump price adjustments, and economic impact of fuel pricing decisions by the government and NNPC."
    }
}
```

**Why good:**
- Mentions key terms: "fuel", "pricing", "subsidy", "pump price"
- Includes context: "in Nigeria", "government", "NNPC"
- Covers related concepts: "economic impact", "petroleum products"
- Specific enough for good embeddings

❌ **Bad Example:**
```json
{
    "fuel_pricing": {
        "description": "Fuel prices"  // Too short, not enough context
    }
}
```

**Why bad:**
- Too vague
- Missing context
- Won't generate good embeddings
- Poor similarity matching

### Real-World Example
```json
{
    "presidential_announcements": {
        "description": "Official statements, declarations, and announcements made by the President of Nigeria. Includes presidential speeches, policy announcements, executive orders, state of the nation addresses, press conferences, and public statements from the presidency. Covers major policy decisions, cabinet appointments, national addresses, and presidential communications to the public."
    }
}
```

**Key elements:**
- Who: "President of Nigeria"
- What: "statements, declarations, announcements"
- Examples: "speeches", "executive orders", "press conferences"
- Context: "presidency", "public communications"

---

## 3. `keywords` Field

### Purpose
**Array of keywords for fast keyword-based matching**. Used for:
- Initial filtering (fast keyword matching)
- Fallback when embeddings unavailable
- Boosting confidence scores
- Quick relevance checks

### Characteristics
- **Relevant terms**: Words/phrases that appear in mentions about this topic
- **Variations included**: Different ways people refer to the topic
- **Common misspellings**: If applicable
- **5-15 keywords**: Enough coverage, not too many

### How It's Used
1. **Keyword Matching**: Count how many keywords appear in mention text
2. **Scoring**: More matches = higher keyword score
3. **Combined with Embeddings**: Keyword score + embedding score = final confidence

### Examples

✅ **Good Example:**
```json
{
    "fuel_pricing": {
        "keywords": [
            "fuel",
            "petrol",
            "diesel",
            "subsidy",
            "pump price",
            "pricing",
            "gasoline",
            "pms",
            "pms price",
            "refinery",
            "petroleum price"
        ]
    }
}
```

**Why good:**
- Covers main terms: "fuel", "petrol", "diesel"
- Includes variations: "pump price", "pms price", "petroleum price"
- Includes related terms: "subsidy", "refinery"
- Covers abbreviations: "pms" (Premium Motor Spirit)

❌ **Bad Example:**
```json
{
    "fuel_pricing": {
        "keywords": ["fuel"]  // Too few, misses variations
    }
}
```

**Why bad:**
- Only one keyword
- Misses "petrol", "diesel", "subsidy"
- Poor matching coverage

### Keyword Selection Tips

1. **Think like a user**: What words would someone use when talking about this?
2. **Include synonyms**: "petrol" = "gasoline" = "fuel"
3. **Include related terms**: "subsidy" related to "fuel pricing"
4. **Common phrases**: "pump price", "fuel subsidy"
5. **Abbreviations**: "pms", "nnpc" (if commonly used)

### Real-World Example
```json
{
    "asuu_strikes": {
        "keywords": [
            "asuu",
            "strike",
            "lecturers",
            "academic staff",
            "university strike",
            "asuu strike",
            "lecturer strike",
            "academic union",
            "university lecturers",
            "asuu industrial action"
        ]
    }
}
```

**Coverage:**
- Organization: "asuu"
- Action: "strike", "industrial action"
- People: "lecturers", "academic staff"
- Phrases: "university strike", "asuu strike"

---

## 4. `category` Field

### Purpose
**Optional grouping for organization and filtering**. Used for:
- Organizing topics in admin interfaces
- Filtering topics by category
- Analytics and reporting
- Topic management

### Characteristics
- **Optional**: Can be omitted if not needed
- **Broad grouping**: High-level category
- **Consistent naming**: Use same categories across topics

### Common Categories

```json
"category": "energy"           // Energy-related topics
"category": "education"         // Education-related topics
"category": "security"          // Security and defense
"category": "economy"           // Economic and financial
"category": "health"            // Health and healthcare
"category": "executive"         // Presidential/executive actions
"category": "infrastructure"    // Infrastructure and development
"category": "governance"         // General governance
```

### Examples

✅ **Good Example:**
```json
{
    "fuel_pricing": {
        "category": "energy"
    },
    "oil_exploration": {
        "category": "energy"
    },
    "renewable_energy": {
        "category": "energy"
    }
}
```

**Benefits:**
- All energy topics grouped together
- Easy to filter: "Show all energy topics"
- Better organization in admin panels

### When to Use Categories

**Use categories when:**
- You have many topics (20+)
- You want to organize topics
- You need category-based filtering
- You want category-level analytics

**Skip categories when:**
- You have few topics (< 10)
- Organization not needed
- Simple use case

---

## Complete Example

Here's a complete topic definition with all fields:

```json
{
    "fuel_pricing": {
        "name": "Fuel Pricing",
        "description": "Fuel pricing policies, subsidies, and pump price changes affecting petroleum products in Nigeria. Includes discussions about petrol, diesel, gasoline pricing, fuel subsidy removal or implementation, pump price adjustments, and economic impact of fuel pricing decisions by the government and NNPC. Covers both increases and decreases in fuel prices, subsidy policies, and public reactions to pricing changes.",
        "keywords": [
            "fuel",
            "petrol",
            "diesel",
            "subsidy",
            "pump price",
            "pricing",
            "gasoline",
            "pms",
            "pms price",
            "refinery",
            "petroleum price",
            "fuel cost",
            "petrol price",
            "diesel price"
        ],
        "category": "energy"
    }
}
```

### Field Breakdown

| Field | Value | Purpose |
|-------|-------|---------|
| **name** | "Fuel Pricing" | Display name for dashboards |
| **description** | Long detailed text... | Used to generate embedding vector |
| **keywords** | ["fuel", "petrol", ...] | Fast keyword matching |
| **category** | "energy" | Organization/grouping |

---

## How Fields Work Together

### Classification Process

1. **Keyword Matching** (Fast):
   - Count keywords in mention text
   - Calculate keyword score (0.0-1.0)

2. **Embedding Similarity** (Accurate):
   - Compare mention embedding to topic embedding (from description)
   - Calculate similarity score (0.0-1.0)

3. **Combined Score**:
   ```
   final_score = (0.3 × keyword_score) + (0.7 × embedding_score)
   ```

4. **Category** (Optional):
   - Used for filtering/organization
   - Not used in classification scoring

### Example Flow

**Mention**: "Government announces removal of fuel subsidy, petrol prices expected to rise"

**Topic**: `fuel_pricing`

1. **Keyword Match**:
   - Found: "fuel", "subsidy", "petrol", "prices"
   - Score: 4/14 keywords = 0.29 (normalized)

2. **Embedding Similarity**:
   - Mention embedding vs. topic embedding
   - Cosine similarity: 0.87

3. **Combined**:
   - (0.3 × 0.29) + (0.7 × 0.87) = 0.696
   - **Confidence: 0.696** ✅ Above threshold

4. **Result**: Mention classified into `fuel_pricing` topic

---

## Best Practices

### ✅ DO

1. **Descriptions**: Be detailed and context-rich
2. **Keywords**: Include variations and synonyms
3. **Names**: Use clear, human-readable names
4. **Categories**: Use consistently across topics

### ❌ DON'T

1. **Descriptions**: Don't be too vague or too short
2. **Keywords**: Don't use only one keyword
3. **Names**: Don't use technical slugs as names
4. **Categories**: Don't create too many categories (5-10 is good)

---

## Quick Reference

| Field | Required | Used For | Example |
|-------|----------|----------|---------|
| `name` | ✅ Yes | Display, UI | "Fuel Pricing" |
| `description` | ✅ Yes | Embedding generation | "Fuel pricing policies..." |
| `keywords` | ✅ Yes | Keyword matching | ["fuel", "petrol", ...] |
| `category` | ❌ Optional | Organization | "energy" |

---

*Topic Definition Guide v1.0*

