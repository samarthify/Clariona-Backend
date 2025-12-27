# Executive Overview: Content Classification Flow

## Overview
This document provides an executive-level overview of how incoming mentions are processed and classified through our multi-stage analysis pipeline. The system transforms raw content into structured, categorized data suitable for governance analysis and reporting.

---

## Classification Pipeline Flow

```
Incoming Mention
    ↓
┌─────────────────────────────────────────┐
│ STEP 1: SENTIMENT CLASSIFICATION       │
│ (Presidential Perspective Analysis)     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ STEP 2: TOPIC CLASSIFICATION            │
│ (36 Federal Topic Categories)          │
│ - Method A: AI-Based Classification      │
│ - Method B: Keyword-Based Fallback     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ STEP 3: VALIDATION & ENRICHMENT        │
│ (Match to Predefined Topic List)       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ STEP 4: ISSUE CLASSIFICATION           │
│ (Dynamic Issue Extraction from Topics)  │
└─────────────────────────────────────────┘
    ↓
Final Classified Result
```

---

## Step 1: Sentiment Classification

### Purpose
Analyze content from the President's strategic perspective to determine how it impacts presidential image, agenda, or political capital.

### Process
1. **Input**: Raw text content from collected mentions
2. **Analysis Method**: AI-powered sentiment analysis using OpenAI models
3. **Output**: 
   - **Sentiment Label**: `positive`, `negative`, or `neutral`
   - **Sentiment Score**: Numerical score (-1.0 to 1.0)
   - **Justification**: Brief explanation of the classification
   - **Relevant Topics**: Key topics identified in the content

### Classification Criteria
- **POSITIVE**: Strengthens presidential image, agenda, or political capital
- **NEGATIVE**: Threatens presidential image, credibility, or agenda
- **NEUTRAL**: No material impact on presidency or requires monitoring

### Key Features
- Uses presidential perspective (not general sentiment)
- Considers strategic impact on governance
- Provides justification for transparency
- Extracts relevant topics for context

---

## Step 2: Topic Classification

After sentiment is determined, the content is classified into one of **36 predefined federal topic categories** (referred to as "topics" instead of ministries).

### Two Classification Methods

---

### Method A: AI-Based Topic Classification (Primary)

#### How It Works
1. **Prompt Construction**: 
   - System creates a structured prompt containing:
     - The text content (first 800 characters)
     - Complete list of all 36 topic categories with exact keys
     - Instructions to return JSON format

2. **AI Analysis**:
   - Sends prompt to OpenAI API (using models: gpt-5-mini, gpt-5-nano, gpt-4.1-mini, or gpt-4.1-nano)
   - AI model analyzes semantic meaning and context
   - Determines most appropriate topic category

3. **Response Format**:
   ```json
   {
       "topic_category": "petroleum_resources",
       "governance_relevance": 0.9,
       "confidence": 0.85,
       "keywords": ["fuel", "subsidy", "pricing"],
       "reasoning": "Content discusses fuel subsidy removal policy"
   }
   ```

#### Advantages
- **Semantic Understanding**: Understands context, not just keywords
- **Nuanced Classification**: Can handle complex, multi-faceted content
- **High Accuracy**: Leverages advanced language model capabilities
- **Contextual Awareness**: Considers Nigerian governance context

#### Example
- **Text**: "The government's decision to remove fuel subsidies has sparked nationwide protests"
- **AI Analysis**: Recognizes this relates to petroleum resources policy
- **Result**: `petroleum_resources` with high confidence

---

### Method B: Keyword-Based Fallback Classification

#### When Used
- OpenAI API is unavailable
- API calls fail after retry attempts
- Rate limiting prevents API access

#### How It Works
1. **Keyword Mapping**: 
   - Predefined keyword lists for ~20 common topics
   - Each topic has associated keywords (e.g., `petroleum_resources`: ["oil", "gas", "petroleum", "fuel"])

2. **Keyword Matching**:
   - Text is converted to lowercase
   - System searches for keyword matches in the text
   - Counts matches per topic category

3. **Selection**:
   - Topic with highest keyword match count is selected
   - If no matches found, defaults to `non_governance`

#### Advantages
- **Reliability**: Works without API dependencies
- **Speed**: Fast keyword matching
- **Transparency**: Clear matching logic

#### Limitations
- **Less Accurate**: May miss nuanced content
- **Limited Coverage**: Only ~20 topics have keyword mappings
- **No Context Understanding**: Pure keyword matching

#### Example
- **Text**: "Oil prices increased due to global market conditions"
- **Keyword Match**: Finds "oil" → matches `petroleum_resources`
- **Result**: `petroleum_resources` (with lower confidence than AI method)

---

## Step 3: Validation & Enrichment

After topic classification (via either method), the result undergoes validation and enrichment.

### Validation Process

1. **Topic Key Validation**:
   - Checks if classified topic key exists in predefined list of 36 topics
   - If invalid key is returned, defaults to `non_governance`

2. **Topic Name Mapping**:
   - Maps topic key to human-readable display name
   - Example: `petroleum_resources` → "Petroleum Resources"

3. **Metadata Enrichment**:
   - **Category Type**: Determines if topic is governance-related
   - **Page Type**: Based on sentiment:
     - `'issues'` if sentiment is `'negative'`
     - `'positive_coverage'` if sentiment is `'positive'`
     - `'issues'` for `'neutral'` (default)
   - **Governance Relevance**: Score indicating how relevant to governance (0.0-1.0)
   - **Confidence**: Classification confidence score (0.0-1.0)
   - **Keywords**: Extracted relevant keywords
   - **Is Governance Content**: Boolean flag (relevance ≥ 0.3)

### Predefined Topic List

The system validates against **36 federal topic categories**:

1. Agriculture & Food Security
2. Aviation & Aerospace Development
3. Budget & Economic Planning
4. Communications & Digital Economy
5. Defence
6. Education
7. Environment & Ecological Management
8. Finance
9. Foreign Affairs
10. Health & Social Welfare
11. Housing & Urban Development
12. Humanitarian Affairs & Poverty Alleviation
13. Industry, Trade & Investment
14. Interior
15. Justice
16. Labour & Employment
17. Marine & Blue Economy
18. Niger Delta Development
19. Petroleum Resources
20. Power
21. Science & Technology
22. Solid Minerals Development
23. Sports Development
24. Tourism
25. Transportation
26. Water Resources & Sanitation
27. Women Affairs
28. Works
29. Youth Development
30. Livestock Development
31. Information & Culture
32. Police Affairs
33. Steel Development
34. Special Duties & Inter-Governmental Affairs
35. Federal Capital Territory Administration
36. Art, Culture & Creative Economy

Plus: `non_governance` for content not related to governance

---

## Step 4: Issue Classification from Topics

Once a topic is identified and validated, the system extracts specific **issues** within that topic.

### Purpose
Transform broad topic classifications into specific, actionable issue labels that can be tracked and analyzed over time.

### How Issues Are Obtained

#### Dynamic Issue Creation System

The system maintains a **dynamic list of up to 20 issues per topic**, created and managed automatically:

1. **Issue Storage**:
   - Each topic has a JSON file storing its issues
   - Location: `topic_issues/{topic_key}.json`
   - Structure:
     ```json
     {
         "topic": "petroleum_resources",
         "issue_count": 5,
         "max_issues": 20,
         "issues": [
             {
                 "slug": "fuel-subsidy-removal",
                 "label": "Fuel Subsidy Removal",
                 "mention_count": 150,
                 "created_at": "2025-11-02T10:00:00",
                 "last_updated": "2025-11-02T15:30:00"
             },
             ...
         ]
     }
     ```

2. **Issue Classification Process**:

   **Scenario A: No Existing Issues**
   - If topic has no issues yet, creates first issue from the mention
   - AI generates issue slug and label from content
   - Stores in topic's issue file

   **Scenario B: Issues Exist (Under 20 Limit)**
   - Compares mention to existing issues using AI
   - AI determines if mention matches existing issue or is new
   - **If Matches**: Updates mention count for existing issue
   - **If New**: Creates new issue (if under 20 limit)

   **Scenario C: At 20 Issue Limit**
   - System has reached maximum of 20 issues per topic
   - Forces matching to existing issues only
   - No new issues can be created
   - Consolidates similar content into existing issues

3. **Issue Matching Logic**:
   - Uses AI to compare mention text to existing issue labels
   - Determines semantic similarity
   - Returns match decision with confidence score
   - Updates issue metadata (mention count, last updated timestamp)

#### Example Flow

**Input**: 
- Topic: `petroleum_resources`
- Text: "Government announces removal of fuel subsidies, prices expected to rise"

**Process**:
1. Load existing issues for `petroleum_resources`
2. AI compares text to existing issues:
   - Existing: "Fuel Subsidy Removal" (150 mentions)
   - AI determines: **MATCH** (high similarity)
3. Update existing issue:
   - Increment mention count: 150 → 151
   - Update last_updated timestamp
4. Return: `("fuel-subsidy-removal", "Fuel Subsidy Removal")`

**Alternative (New Issue)**:
- If text discusses "Oil Pipeline Vandalism" and no similar issue exists
- AI determines: **NEW ISSUE**
- Creates: `("oil-pipeline-vandalism", "Oil Pipeline Vandalism")`
- Adds to topic's issue list

### Issue Management Features

- **Automatic Creation**: Issues created dynamically from content
- **Semantic Matching**: AI understands similar issues even with different wording
- **Mention Tracking**: Counts how many times each issue is mentioned
- **Limit Enforcement**: Maximum 20 issues per topic prevents fragmentation
- **Consolidation**: At limit, forces matching to prevent new issue creation
- **Persistence**: Issues stored in JSON files for continuity

---

## Complete Classification Result

After all steps, each mention receives a complete classification:

```json
{
    // Sentiment (Step 1)
    "sentiment_label": "negative",
    "sentiment_score": -0.8,
    "sentiment_justification": "Content criticizes government policy",
    
    // Topic (Step 2 + 3)
    "topic_hint": "petroleum_resources",
    "topic_category": "petroleum_resources",
    "category_label": "Petroleum Resources",
    "governance_relevance": 0.9,
    "confidence": 0.85,
    "keywords": ["fuel", "subsidy", "pricing"],
    
    // Issue (Step 4)
    "issue_slug": "fuel-subsidy-removal",
    "issue_label": "Fuel Subsidy Removal",
    "issue_confidence": 0.92,
    
    // Metadata
    "page_type": "issues",
    "is_governance_content": true,
    "category_type": "governance"
}
```

---

## Key Benefits

1. **Multi-Stage Refinement**: Each step adds specificity and accuracy
2. **Dual Classification Methods**: AI primary, keyword fallback ensures reliability
3. **Dynamic Issue Extraction**: Automatically identifies and tracks specific issues
4. **Validation & Enrichment**: Ensures data quality and completeness
5. **Presidential Perspective**: Sentiment analysis considers strategic impact
6. **Scalable Architecture**: Handles high volumes with parallel processing

---

## Technical Implementation

- **Models Used**: gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano
- **Processing**: Parallel pipelines across multiple models
- **Storage**: JSON files for issue persistence
- **Rate Limiting**: Multi-model rate limiter prevents API overload
- **Error Handling**: Automatic fallback mechanisms at each stage

---

*Document Version: 1.0*  
*Last Updated: December 2024*

