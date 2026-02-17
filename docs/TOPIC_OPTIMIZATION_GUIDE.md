# Topic Optimization Guide: Identifying Excellent Topics

This guide provides instructions for configuring high-performing topics in the Clariona system. It analyzes the underlying classification logic and offers actionable recommendations for crafting "excellent" keywords and descriptions.

## 1. System Analysis: Tracing the Flow

Understanding how the system "thinks" is the first step to optimization. The `TopicClassifier` uses a **Hybrid Scoring System** that combines strict keyword matching with semantic understanding.

### The Classification Flow

1.  **Input**: The system receives a mention (text) and its pre-computed embedding vector (OpenAI `text-embedding-3-small`).
2.  **Parallel Analysis**:
    *   **Path A: Keyword Matching (40% Weight)**
        *   Checks for exact matches or lemmatized matches (if spaCy is enabled).
        *   **Boosts**: Whole word matches get a 1.2x boost.
        *   **Logic**: Supports `OR` lists and complex `AND/OR` groups.
    *   **Path B: Semantic Similarity (60% Weight)**
        *   Compares the **input text's embedding** with the **Topic's Embedding**.
        *   **Crucial Note**: The Topic Embedding is generated strictly from: `"{Topic Name} {Topic Description}"`.
3.  **Scoring & Decision**:
    *   `Final Score = (0.4 * Keyword_Score) + (0.6 * Embedding_Score)`
    *   **Synergy Boost**: If *both* scores are decent (>0.15 for keywords, >0.25 for embedding), the score is boosted by 15%.
    *   **Threshold**: Only topics satisfying the `min_score_threshold` (default 0.2) are returned.

---

## 2. Instructions for "Excellent" Topics

To achieve "excellent" performance, you must optimize for both paths of the system.

### A. Optimizing Descriptions (The 60%)

Since 60% of the score comes from the description, this is where most optimizations fail. A weak description yields a weak semantic signal.

*   **Instruction 1: Be Verbose & Contextual**
    *   **Bad**: "Hospitals."
    *   **Good**: "Public and private hospital facilities, primary healthcare centers, medical infrastructure, and patient care delivery systems in Nigeria."
    *   *Why?* The embedding model needs context to place the vector in the correct semantic space.

*   **Instruction 2: Use "Semantic Expansion"**
    *   Include words that describe the *problems*, *actions*, and *actors* related to the topic, not just the nouns.
    *   *Example*: For "Education", include "strikes", "tuition", "syllabus", "ASUU", "literacy".

*   **Instruction 3: Differentiate Closely Related Topics**
    *   If you have "Maternal Health" and "Child Health", ensure their descriptions explicitly mention their specific focus to push their embedding vectors apart.

### B. Optimizing Keywords (The 40%)

Keywords provide the precision that embeddings sometimes miss.

*   **Instruction 1: Use `keyword_groups` for Specificity**
    *   Avoid generic single words like "money" or "rights". They trigger false positives.
    *   Use **AND Groups**: Instead of just "rights", use `["human", "rights"]` (Group Type: AND).
    *   *Code Structure*:
        ```json
        "keyword_groups": {
            "groups": [
                {"type": "and", "keywords": ["human", "rights"]},
                {"type": "or", "keywords": ["amnesty international", "hrc"]}
            ]
        }
        ```

*   **Instruction 2: Leverage "Whole Word" Matching**
    *   The system boosts whole-word matches (e.g., "act" vs "action"). Ensure your important keywords stand alone well.

*   **Instruction 3: Do Not Rely on Plurals (If spaCy Enabled)**
    *   The system (if configured) uses lemmatization. "Bank" matches "Banks", "Banking", "Banked". You don't need to list every variation.

---

## 3. Recommendations & Best Practices

### Recommendation 1: Audit & Enable spaCy
**Status**: The code checks for `spacy`.
**Recommendation**: Ensure `spacy` and `en_core_web_sm` are installed in the production environment.
*   *Why?* It enables "Lemmatization" and "Phrase Matching", significantly reducing the need for massive keyword lists and improving accuracy.

### Recommendation 2: The "Golden Description" Standard
Adopt a standard format for all topic descriptions to ensure consistent embedding quality:
> "[Topic Name] covers [Core Concept], [Synonym 1], and [Synonym 2]. It includes discussions regarding [Related Sub-concept A], [Related Sub-concept B], and issues involving [Key Actor/Stakeholder]."

### Recommendation 3: Test-Driven Topic Design
Don't guess. Use a script to test new topics against real data before committing.

**Procedure**:
1.  Extract 50 random texts from your database.
2.  Run them through `TopicClassifier` with your candidate topic.
3.  **Tweak Description**: If it misses relevant texts, add the missing context words to the description.
4.  **Tweak Keywords**: If it catches irrelevant texts, convert single keywords into "AND" groups.

### Recommendation 4: Regular "Missed Topic" Analysis
Monitor mentions that receive **no** topic classification or low confidence scores.
1.  Filter database for `topic = null` or entries with `confidence < 0.3`.
2.  Cluster these texts to find emerging themes.
3.  Create new topics for these themes.

### Recommendation 5: Stop-Word Removal in Keywords
Ensure your keyword lists do **not** contain stop words ("the", "in", "at").
*   *Why?* "The bank" as a keyword might match "The" in a completely unrelated sentence if not handled correctly (though the code tries to handle this, it's safer to be clean).

## Summary Checklist for New Topics

- [ ] **Name**: Clear and distinctive?
- [ ] **Description**: >30 words? Includes synonyms? Includes context (e.g. "Nigeria")?
- [ ] **Keywords**: Specific? No generic single words? Uses AND groups for ambiguity?
- [ ] **Test**: Verified against sample text?

---

## 4. The Perfect Topic Template

Use this template when defining new topics to ensure you capture all necessary optimization points.

### Topic Builder Worksheet

| Component | Standard | Your Draft |
| :--- | :--- | :--- |
| **Topic Key** | snake_case, unique (e.g., `rural_healthcare`) | |
| **Name** | Clear, specific, 2-3 words (e.g., "Rural Healthcare Access") | |
| **Core Concept** | What is this primarily about? | |
| **Synonyms** | List 3-5 alternative ways to say this. | |
| **Context** | Where does this happen? Who is involved? | |
| **Keywords (High Precision)** | Unique words that *always* mean this topic. | |
| **Keywords (Ambiguous)** | Words that need context (Require AND groups). | |

### JSON Configuration Template

```json
"topic_key_here": {
    "name": "Title Case Name",
    "description": "[Name] refers to [Core Concept], including [Synonym 1] and [Synonym 2]. It covers discussions on [Context/Activity A], [Context/Activity B], and involves [Key Stakeholders]. Issues related to [Related Problem] are also included.",
    "keywords": [
        "precise_keyword_1",
        "precise_keyword_2"
    ],
    "keyword_groups": {
        "groups": [
            {
                "type": "and",
                "keywords": ["ambiguous_word", "clarifying_context_word"]
            },
            {
                 "type": "or",
                "keywords": ["synonym_phrase_1", "synonym_phrase_2"]
            }
        ]
    },
    "category": "health"
}
```

