# Subcategory System Design (Not Currently in Use)

## Overview

The subcategory system was designed as an **intermediate classification level** between topics (ministries) and issues. It provides a structured, predefined set of subcategories (3-5 per topic) that represent the main functional areas within each topic.

## Current System vs. Intended Subcategory System

### Current System (Active)
```
Level 1: Topic Classification (36 topics)
    ↓
Level 2: Dynamic Issue Classification (up to 20 issues per topic, created dynamically)
```

### Intended Subcategory System (Not Implemented)
```
Level 1: Topic Classification (36 topics)
    ↓
Level 2: Subcategory Classification (3-5 predefined subcategories per topic)
    ↓
Level 3: Issue Classification (dynamic issues within subcategory)
```

## How Subcategories Were Intended to Work

### 1. Structure

Each topic has **3-5 predefined subcategories** that represent the main functional areas:

**Example: Education Topic**
```python
"education": {
    "primary_education": "Primary Education",
    "secondary_education": "Secondary Education",
    "higher_education": "Higher Education",
    "vocational_training": "Vocational Training",
    "educational_policy": "Educational Policy"
}
```

**Example: Petroleum Resources Topic**
```python
"petroleum_resources": {
    "oil_gas_exploration": "Oil & Gas Exploration",
    "petroleum_policy": "Petroleum Policy",
    "energy_security": "Energy Security",
    "downstream_operations": "Downstream Operations"
}
```

### 2. Classification Flow (Intended)

#### Step 1: Topic Classification
- Content is first classified into one of 36 topics (e.g., `education`, `petroleum_resources`)

#### Step 2: Subcategory Classification (Not Currently Implemented)
- After topic is identified, content would be classified into one of the topic's subcategories
- This would use AI to determine which subcategory best fits the content
- Example: Topic `education` → Subcategory `higher_education`

#### Step 3: Issue Classification
- Within the identified subcategory, dynamic issues would be created/tracked
- Issues would be more specific than subcategories
- Example: Subcategory `higher_education` → Issue `"ASUU Strike"` or `"University Funding Crisis"`

### 3. Intended Benefits

1. **Structured Hierarchy**: 
   - Topic → Subcategory → Issue provides clear hierarchical organization
   - More organized than jumping directly from topic to issues

2. **Consistent Categorization**:
   - Predefined subcategories ensure consistent classification across similar content
   - Prevents fragmentation that can occur with purely dynamic issues

3. **Better Analytics**:
   - Can analyze trends at subcategory level (e.g., all "Higher Education" issues)
   - Provides intermediate granularity between broad topics and specific issues

4. **Guided Issue Creation**:
   - Issues would be created within subcategory context
   - Helps ensure issues are properly scoped and related

## Why It's Not Currently Used

### Current Implementation Choice

The system currently uses **dynamic issue classification** directly from topics, skipping the subcategory level. This approach was chosen because:

1. **Flexibility**: Dynamic issues can adapt to emerging topics without being constrained by predefined subcategories
2. **Simplicity**: Two-level hierarchy (Topic → Issue) is simpler than three-level (Topic → Subcategory → Issue)
3. **Granularity**: Issues can be as specific as needed without being limited to subcategory boundaries
4. **Real-world Adaptation**: Issues emerge organically from content rather than being forced into predefined boxes

### Current System Advantages

- **More Adaptive**: Can handle new types of content that don't fit predefined subcategories
- **Less Maintenance**: No need to maintain and update subcategory definitions
- **Issue-Driven**: Focuses on actual issues mentioned in content rather than abstract categories
- **Simpler Logic**: Fewer classification steps means faster processing

## How Subcategories Could Be Integrated

If the subcategory system were to be implemented, it would work as follows:

### Modified Classification Flow

```python
# Step 1: Topic Classification (Current - Active)
topic = classify_topic(text)  # e.g., "education"

# Step 2: Subcategory Classification (Would be added)
subcategory = classify_subcategory(text, topic)  # e.g., "higher_education"

# Step 3: Issue Classification (Current - Active, but scoped to subcategory)
issue = classify_issue(text, topic, subcategory)  # e.g., "asuu-strike"
```

### Implementation Example

```python
def classify_with_subcategory(text: str, topic: str) -> Dict:
    """
    Classify content through topic → subcategory → issue hierarchy.
    """
    # Get available subcategories for this topic
    subcategories = get_ministry_subcategories(topic)
    
    # Use AI to classify into subcategory
    subcategory_key = ai_classify_subcategory(text, topic, subcategories)
    
    # Then classify issue within subcategory
    issue_slug, issue_label = classify_issue(text, topic, subcategory_key)
    
    return {
        'topic': topic,
        'subcategory': subcategory_key,
        'subcategory_label': subcategories.get(subcategory_key),
        'issue_slug': issue_slug,
        'issue_label': issue_label
    }
```

### Prompt Structure (Hypothetical)

```python
def create_subcategory_prompt(text: str, topic: str, subcategories: Dict) -> str:
    return f"""Classify this content into one of the subcategories for {topic}.

Text: "{text[:800]}"

Available Subcategories:
{format_subcategories(subcategories)}

Return JSON:
{{
    "subcategory": "subcategory_key",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}
"""
```

## Subcategory Data Structure

### Current Definition

All 36 topics have subcategories defined in `MINISTRY_SUBCATEGORIES`:

```python
MINISTRY_SUBCATEGORIES = {
    "education": {
        "primary_education": "Primary Education",
        "secondary_education": "Secondary Education",
        "higher_education": "Higher Education",
        "vocational_training": "Vocational Training",
        "educational_policy": "Educational Policy"
    },
    "petroleum_resources": {
        "oil_gas_exploration": "Oil & Gas Exploration",
        "petroleum_policy": "Petroleum Policy",
        "energy_security": "Energy Security",
        "downstream_operations": "Downstream Operations"
    },
    # ... 34 more topics
}
```

### Helper Functions Available

The codebase includes helper functions for subcategories (though not used):

```python
# Get subcategories for a specific topic
get_ministry_subcategories(topic_key)  # Returns dict of subcategories

# Get all subcategories from all topics
get_all_subcategories()  # Returns flattened dict of all subcategories
```

## Comparison: Subcategory vs. Current Issue System

| Aspect | Subcategory System (Intended) | Current Issue System (Active) |
|--------|------------------------------|-------------------------------|
| **Structure** | Predefined (3-5 per topic) | Dynamic (up to 20 per topic) |
| **Flexibility** | Limited to predefined options | Adapts to any content |
| **Consistency** | High (same subcategories always) | Variable (depends on content) |
| **Granularity** | Medium (functional areas) | High (specific issues) |
| **Maintenance** | Requires updates to definitions | Self-maintaining |
| **Hierarchy** | 3 levels (Topic → Subcategory → Issue) | 2 levels (Topic → Issue) |
| **Use Case** | Structured, consistent categorization | Adaptive, content-driven classification |

## Potential Use Cases for Subcategories

If implemented, subcategories could be useful for:

1. **Reporting & Analytics**: 
   - "Show me all Higher Education issues" (subcategory-level filtering)
   - Trend analysis by subcategory

2. **Issue Organization**:
   - Group related issues under subcategories
   - Better navigation and filtering

3. **Validation**:
   - Ensure issues are created within appropriate subcategory context
   - Prevent misclassification

4. **Structured Queries**:
   - "All issues in Education → Higher Education"
   - More precise filtering than topic alone

## Conclusion

The subcategory system represents a **more structured, hierarchical approach** to classification, but the current system's **flexibility and adaptability** were prioritized. The subcategory definitions remain in the codebase and could be activated if a more structured classification approach is desired in the future.

---

*Note: The subcategory system is fully defined but not integrated into the classification pipeline. All subcategory data is available via helper functions but is not used during content classification.*

