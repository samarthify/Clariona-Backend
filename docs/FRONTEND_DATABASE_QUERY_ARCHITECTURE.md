# Frontend Database Query Architecture
## How the Frontend Accesses Data

**Created**: January 27, 2025  
**Purpose**: Explain the data flow from Frontend → Backend API → Database

---

## ⚠️ Critical Architecture Principle

**The frontend NEVER directly queries the database.**

Instead, the frontend queries the database through a **Backend API layer** that:
- Provides security (authentication, authorization)
- Handles business logic
- Optimizes queries
- Caches responses
- Enforces data access rules

---

## Complete Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Dashboard   │  │    Issues    │  │    Alerts    │     │
│  │   Component   │  │   Component  │  │  Component   │     │
│  └───────┬───────┘  └───────┬──────┘  └───────┬──────┘     │
│          │                  │                  │            │
│          └──────────────────┴──────────────────┘            │
│                           │                                  │
│                    ┌───────▼────────┐                        │
│                    │  API Client    │                        │
│                    │  (Axios/RTK)   │                        │
│                    └───────┬────────┘                        │
└────────────────────────────┼────────────────────────────────┘
                             │
                    HTTP/HTTPS Request
                    (with JWT token)
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              BACKEND API (FastAPI/Python)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                        │   │
│  │  GET /api/v1/dashboard/national                      │   │
│  │  GET /api/v1/issues                                  │   │
│  │  GET /api/v1/alerts                                  │   │
│  │  GET /api/v1/sentiment/national                      │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                        │
│          ┌───────────┴───────────┐                          │
│          │                        │                          │
│  ┌───────▼────────┐      ┌───────▼────────┐                 │
│  │  Authentication│      │  Authorization │                 │
│  │  (JWT Verify)  │      │  (Role Check)  │                 │
│  └───────┬────────┘      └───────┬────────┘                 │
│          │                        │                          │
│          └───────────┬────────────┘                          │
│                      │                                        │
│              ┌───────▼────────┐                               │
│              │  Service Layer │                               │
│              │  (Business     │                               │
│              │   Logic)       │                               │
│              └───────┬────────┘                               │
│                      │                                        │
│              ┌───────▼────────┐                               │
│              │  Data Access    │                               │
│              │  Layer (DAL)    │                               │
│              └───────┬────────┘                               │
└──────────────────────┼────────────────────────────────────────┘
                       │
              SQLAlchemy ORM
              (SQL queries)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              DATABASE (PostgreSQL)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tables:                                              │   │
│  │  • sentiment_data                                     │   │
│  │  • topics                                             │   │
│  │  • mention_topics                                     │   │
│  │  • topic_issues                                       │   │
│  │  • issue_mentions                                     │   │
│  │  • sentiment_aggregations                             │   │
│  │  • sentiment_trends                                   │   │
│  │  • alerts                                             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer-by-Layer Breakdown

### 1. Frontend Layer (React/TypeScript)

**What it does**:
- Makes HTTP requests to backend API
- Handles UI state and user interactions
- Displays data from API responses

**Example**:
```typescript
// Frontend component
import { useGetNationalDashboardQuery } from './api/dashboardApi';

const Dashboard = () => {
  // RTK Query automatically handles:
  // - HTTP request to GET /api/v1/dashboard/national
  // - Loading state
  // - Error handling
  // - Caching
  const { data, isLoading, error } = useGetNationalDashboardQuery();
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;
  
  return (
    <div>
      <MetricCard label="Sentiment Index" value={data.sentimentIndex} />
      <IssuesList issues={data.topIssues} />
    </div>
  );
};
```

**Key Points**:
- Frontend **never** writes SQL queries
- Frontend **never** connects directly to database
- All data access goes through API endpoints

---

### 2. API Client Layer (Frontend)

**What it does**:
- Manages HTTP requests/responses
- Handles authentication (JWT tokens)
- Provides caching (RTK Query)
- Error handling

**Implementation** (RTK Query):
```typescript
// src/api/dashboardApi.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const dashboardApi = createApi({
  reducerPath: 'dashboardApi',
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/v1',
    prepareHeaders: (headers, { getState }) => {
      // Add JWT token to every request
      const token = selectToken(getState());
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  endpoints: (builder) => ({
    // National dashboard endpoint
    getNationalDashboard: builder.query<DashboardData, void>({
      query: () => '/dashboard/national',
      // Cache for 30 seconds
      keepUnusedDataFor: 30,
    }),
    
    // Issues endpoint with filters
    getIssues: builder.query<Issue[], IssueFilters>({
      query: (filters) => ({
        url: '/issues',
        params: filters, // ?priority=critical&topic=fuel_pricing
      }),
    }),
    
    // Alerts endpoint
    getAlerts: builder.query<Alert[], AlertFilters>({
      query: (filters) => ({
        url: '/alerts',
        params: filters,
      }),
    }),
  }),
});
```

**Alternative** (Axios):
```typescript
// src/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
});

// Add JWT token to every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Usage in component
const fetchDashboard = async () => {
  const response = await apiClient.get('/dashboard/national');
  return response.data;
};
```

---

### 3. Backend API Layer (FastAPI)

**What it does**:
- Receives HTTP requests from frontend
- Authenticates requests (JWT verification)
- Authorizes access (role-based checks)
- Executes business logic
- Queries database via SQLAlchemy ORM
- Returns JSON responses

**Example Endpoint**:
```python
# src/api/dashboard_service.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..auth import get_current_user, require_role
from ..models import SentimentData, MentionTopic, TopicIssue

router = APIRouter(prefix="/api/v1", tags=["dashboard"])

@router.get("/dashboard/national")
async def get_national_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    role: str = Depends(require_role(["president", "ccc_director"]))
):
    """
    Get national dashboard data.
    
    Only accessible to President and CCC Director roles.
    """
    # 1. Query database for sentiment data
    sentiment_data = db.query(SentimentData).filter(
        SentimentData.created_at >= datetime.now() - timedelta(days=7)
    ).all()
    
    # 2. Query for active issues
    active_issues = db.query(TopicIssue).filter(
        TopicIssue.is_active == True,
        TopicIssue.priority_score >= 60  # High or Critical
    ).order_by(TopicIssue.priority_score.desc()).limit(5).all()
    
    # 3. Calculate aggregated metrics
    sentiment_index = calculate_sentiment_index(sentiment_data)
    issue_count = len(active_issues)
    
    # 4. Return JSON response
    return {
        "sentimentIndex": sentiment_index,
        "activeIssues": issue_count,
        "topIssues": [serialize_issue(issue) for issue in active_issues],
        "timestamp": datetime.now().isoformat()
    }
```

**Key Points**:
- Backend API is the **only** layer that queries the database
- All database queries use SQLAlchemy ORM (not raw SQL)
- Business logic is in the service layer
- Responses are JSON (not database rows)

---

### 4. Database Access Layer (SQLAlchemy ORM)

**What it does**:
- Maps Python objects to database tables
- Generates SQL queries
- Handles database connections
- Manages transactions

**Example**:
```python
# src/api/models.py (SQLAlchemy models)
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class SentimentData(Base):
    __tablename__ = "sentiment_data"
    
    entry_id = Column(Integer, primary_key=True)
    text = Column(String)
    sentiment_label = Column(String)
    sentiment_score = Column(Float)
    created_at = Column(DateTime)
    
    # Relationships
    topics = relationship("MentionTopic", back_populates="mention")

class MentionTopic(Base):
    __tablename__ = "mention_topics"
    
    id = Column(UUID, primary_key=True)
    mention_id = Column(Integer, ForeignKey("sentiment_data.entry_id"))
    topic_key = Column(String, ForeignKey("topics.topic_key"))
    topic_confidence = Column(Float)
    
    # Relationships
    mention = relationship("SentimentData", back_populates="topics")
    topic = relationship("Topic", back_populates="mentions")
```

**Query Example**:
```python
# In service layer
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

def get_issues_by_priority(db: Session, min_priority: float = 60):
    """
    Query issues with priority >= min_priority.
    
    SQLAlchemy generates SQL like:
    SELECT * FROM topic_issues 
    WHERE priority_score >= 60 
    ORDER BY priority_score DESC;
    """
    issues = db.query(TopicIssue).filter(
        TopicIssue.priority_score >= min_priority,
        TopicIssue.is_active == True
    ).order_by(
        desc(TopicIssue.priority_score)
    ).all()
    
    return issues
```

---

### 5. Database Layer (PostgreSQL)

**What it does**:
- Stores all data in tables
- Executes SQL queries
- Maintains data integrity
- Provides indexes for performance

**Example Tables**:
```sql
-- sentiment_data table
CREATE TABLE sentiment_data (
    entry_id SERIAL PRIMARY KEY,
    text TEXT,
    sentiment_label VARCHAR(50),
    sentiment_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- topic_issues table
CREATE TABLE topic_issues (
    id UUID PRIMARY KEY,
    issue_slug VARCHAR(200) UNIQUE,
    priority_score FLOAT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_sentiment_created_at ON sentiment_data(created_at);
CREATE INDEX idx_issues_priority ON topic_issues(priority_score DESC);
```

---

## Complete Example: Frontend → Database Query Flow

### Scenario: User views National Dashboard

**Step 1: Frontend Component**
```typescript
// src/features/dashboard/Dashboard.tsx
const Dashboard = () => {
  const { data, isLoading } = useGetNationalDashboardQuery();
  
  return (
    <div>
      <MetricCard value={data?.sentimentIndex} />
      <IssuesList issues={data?.topIssues} />
    </div>
  );
};
```

**Step 2: API Client (RTK Query)**
```typescript
// Automatically makes HTTP request:
// GET /api/v1/dashboard/national
// Headers: Authorization: Bearer <jwt_token>
```

**Step 3: Backend API Endpoint**
```python
# src/api/dashboard_service.py
@router.get("/dashboard/national")
async def get_national_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verify JWT token (in get_current_user dependency)
    # Check role permissions (president or ccc_director)
    
    # Query database
    issues = db.query(TopicIssue).filter(
        TopicIssue.is_active == True,
        TopicIssue.priority_score >= 60
    ).order_by(desc(TopicIssue.priority_score)).limit(5).all()
    
    # Calculate metrics
    sentiment_data = db.query(SentimentData).filter(
        SentimentData.created_at >= datetime.now() - timedelta(days=7)
    ).all()
    
    sentiment_index = calculate_sentiment_index(sentiment_data)
    
    # Return JSON
    return {
        "sentimentIndex": sentiment_index,
        "topIssues": [serialize_issue(i) for i in issues]
    }
```

**Step 4: SQLAlchemy ORM**
```python
# SQLAlchemy generates and executes SQL:
# SELECT * FROM topic_issues 
# WHERE is_active = TRUE AND priority_score >= 60
# ORDER BY priority_score DESC 
# LIMIT 5;
```

**Step 5: PostgreSQL Database**
```sql
-- Executes the SQL query
-- Returns rows from topic_issues table
-- Returns rows from sentiment_data table
```

**Step 6: Response Flow Back**
```
PostgreSQL → SQLAlchemy → FastAPI → JSON Response → 
Frontend API Client → React Component → UI Update
```

---

## API Endpoints Structure

### Required Endpoints for Frontend

**Dashboard Endpoints**:
```
GET  /api/v1/dashboard/national
GET  /api/v1/dashboard/ministry/:ministry_id
GET  /api/v1/dashboard/analyst
```

**Issues Endpoints**:
```
GET    /api/v1/issues                    # List issues (with filters)
GET    /api/v1/issues/:id                # Issue detail
POST   /api/v1/issues/:id/merge          # Merge issues
POST   /api/v1/issues/:id/split          # Split issue
POST   /api/v1/issues/:id/archive        # Archive issue
GET    /api/v1/issues/:id/mentions       # Get mentions for issue
```

**Alerts Endpoints**:
```
GET    /api/v1/alerts                    # List alerts
GET    /api/v1/alerts/:id                # Alert detail
POST   /api/v1/alerts/:id/acknowledge    # Acknowledge alert
POST   /api/v1/alerts/:id/escalate       # Escalate alert
POST   /api/v1/alerts/:id/close          # Close alert
```

**Sentiment Endpoints**:
```
GET    /api/v1/sentiment/national        # National sentiment
GET    /api/v1/sentiment/topic/:key      # Topic sentiment
GET    /api/v1/sentiment/issue/:id        # Issue sentiment
GET    /api/v1/sentiment/trends          # Sentiment trends
```

**Briefings Endpoints**:
```
POST   /api/v1/briefings/generate        # Generate briefing
GET    /api/v1/briefings/:id             # Get briefing
GET    /api/v1/briefings                 # List briefings
```

**Authentication Endpoints**:
```
POST   /api/v1/auth/login                # Login
POST   /api/v1/auth/refresh               # Refresh token
GET    /api/v1/auth/me                    # Current user
POST   /api/v1/auth/logout                # Logout
```

---

## Database Query Patterns

### Pattern 1: Simple Query

**Frontend Request**:
```typescript
GET /api/v1/issues?priority=critical&limit=10
```

**Backend Query**:
```python
@router.get("/issues")
async def get_issues(
    priority: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(TopicIssue)
    
    if priority:
        priority_map = {"critical": 80, "high": 60, "medium": 40}
        min_score = priority_map.get(priority, 0)
        query = query.filter(TopicIssue.priority_score >= min_score)
    
    issues = query.order_by(desc(TopicIssue.priority_score)).limit(limit).all()
    return [serialize_issue(i) for i in issues]
```

**SQL Generated**:
```sql
SELECT * FROM topic_issues 
WHERE priority_score >= 80 
ORDER BY priority_score DESC 
LIMIT 10;
```

---

### Pattern 2: Complex Query with Joins

**Frontend Request**:
```typescript
GET /api/v1/issues/:id/mentions?limit=50
```

**Backend Query**:
```python
@router.get("/issues/{issue_id}/mentions")
async def get_issue_mentions(
    issue_id: UUID,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    # Join issue_mentions → sentiment_data
    mentions = db.query(SentimentData).join(
        IssueMention,
        SentimentData.entry_id == IssueMention.mention_id
    ).filter(
        IssueMention.issue_id == issue_id
    ).order_by(
        desc(SentimentData.created_at)
    ).limit(limit).all()
    
    return [serialize_mention(m) for m in mentions]
```

**SQL Generated**:
```sql
SELECT sentiment_data.* 
FROM sentiment_data
INNER JOIN issue_mentions 
    ON sentiment_data.entry_id = issue_mentions.mention_id
WHERE issue_mentions.issue_id = :issue_id
ORDER BY sentiment_data.created_at DESC
LIMIT 50;
```

---

### Pattern 3: Aggregation Query

**Frontend Request**:
```typescript
GET /api/v1/sentiment/national?time_window=7d
```

**Backend Query**:
```python
@router.get("/sentiment/national")
async def get_national_sentiment(
    time_window: str = "7d",
    db: Session = Depends(get_db)
):
    # Calculate time range
    days = int(time_window.rstrip('d'))
    start_date = datetime.now() - timedelta(days=days)
    
    # Aggregate sentiment
    result = db.query(
        func.avg(SentimentData.sentiment_score).label('avg_sentiment'),
        func.count(SentimentData.entry_id).label('mention_count')
    ).filter(
        SentimentData.created_at >= start_date
    ).first()
    
    # Calculate sentiment index (0-100)
    sentiment_index = (result.avg_sentiment + 1) * 50
    
    return {
        "sentimentIndex": sentiment_index,
        "mentionCount": result.mention_count,
        "timeWindow": time_window
    }
```

**SQL Generated**:
```sql
SELECT 
    AVG(sentiment_score) as avg_sentiment,
    COUNT(entry_id) as mention_count
FROM sentiment_data
WHERE created_at >= :start_date;
```

---

## Security Considerations

### 1. Authentication

**JWT Token Flow**:
```
1. User logs in → POST /api/v1/auth/login
2. Backend validates credentials → Returns JWT token
3. Frontend stores token (httpOnly cookie)
4. Frontend includes token in all requests:
   Authorization: Bearer <token>
5. Backend verifies token on every request
```

### 2. Authorization (Role-Based)

**Backend Checks**:
```python
@router.get("/dashboard/national")
async def get_national_dashboard(
    current_user: dict = Depends(get_current_user),
    role: str = Depends(require_role(["president", "ccc_director"]))
):
    # Only president and ccc_director can access
    # Other roles get 403 Forbidden
    pass
```

### 3. Data Filtering

**Ministry-Specific Filtering**:
```python
@router.get("/dashboard/ministry")
async def get_ministry_dashboard(
    current_user: dict = Depends(get_current_user)
):
    # Filter by user's ministry topics
    ministry_topics = get_ministry_topics(current_user.ministry_id)
    
    issues = db.query(TopicIssue).filter(
        TopicIssue.primary_topic_key.in_(ministry_topics)
    ).all()
    
    return serialize_dashboard(issues)
```

---

## Performance Optimization

### 1. Database Indexes

**Required Indexes**:
```sql
-- For fast issue queries
CREATE INDEX idx_issues_priority ON topic_issues(priority_score DESC);
CREATE INDEX idx_issues_active ON topic_issues(is_active, priority_score);

-- For fast sentiment queries
CREATE INDEX idx_sentiment_created_at ON sentiment_data(created_at);
CREATE INDEX idx_sentiment_score ON sentiment_data(sentiment_score);

-- For fast joins
CREATE INDEX idx_mention_topics_mention ON mention_topics(mention_id);
CREATE INDEX idx_issue_mentions_issue ON issue_mentions(issue_id);
```

### 2. Query Optimization

**Eager Loading** (avoid N+1 queries):
```python
# Bad: N+1 queries
issues = db.query(TopicIssue).all()
for issue in issues:
    mentions = db.query(IssueMention).filter(
        IssueMention.issue_id == issue.id
    ).all()  # Query for each issue!

# Good: Single query with join
issues = db.query(TopicIssue).options(
    joinedload(TopicIssue.mentions)
).all()  # Single query loads all mentions
```

### 3. Caching

**Frontend Caching** (RTK Query):
```typescript
// Cache for 30 seconds
getNationalDashboard: builder.query({
  query: () => '/dashboard/national',
  keepUnusedDataFor: 30,
})
```

**Backend Caching** (Redis):
```python
from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379)

@router.get("/dashboard/national")
async def get_national_dashboard():
    # Check cache first
    cached = redis_client.get("dashboard:national")
    if cached:
        return json.loads(cached)
    
    # Query database
    data = query_dashboard_data()
    
    # Cache for 60 seconds
    redis_client.setex("dashboard:national", 60, json.dumps(data))
    
    return data
```

---

## Error Handling

### Frontend Error Handling

```typescript
const { data, error, isLoading } = useGetNationalDashboardQuery();

if (error) {
  if (error.status === 401) {
    // Unauthorized - redirect to login
    navigate('/login');
  } else if (error.status === 403) {
    // Forbidden - show access denied
    return <AccessDenied />;
  } else {
    // Other error - show error message
    return <ErrorMessage error={error} />;
  }
}
```

### Backend Error Handling

```python
@router.get("/dashboard/national")
async def get_national_dashboard(
    db: Session = Depends(get_db)
):
    try:
        data = query_dashboard_data(db)
        return data
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Summary

### Key Principles

1. **Frontend NEVER queries database directly**
   - All queries go through Backend API
   - Frontend only makes HTTP requests

2. **Backend API is the ONLY database access point**
   - All SQL queries are in the backend
   - Business logic is in the backend
   - Security is enforced in the backend

3. **Database queries use SQLAlchemy ORM**
   - No raw SQL in application code
   - Type-safe queries
   - Automatic query optimization

4. **Authentication & Authorization**
   - JWT tokens for authentication
   - Role-based access control
   - Data filtering by user role

5. **Performance Optimization**
   - Database indexes
   - Query optimization
   - Caching (frontend + backend)

---

## Next Steps

1. **Implement Backend API Endpoints**
   - Create endpoints for all frontend needs
   - Add authentication/authorization
   - Add database queries

2. **Implement Frontend API Client**
   - Setup RTK Query or Axios
   - Create API hooks
   - Add error handling

3. **Test End-to-End**
   - Test frontend → backend → database flow
   - Verify security (auth, authorization)
   - Verify performance

---

**Status**: 📋 **ARCHITECTURE DOCUMENT**  
**Last Updated**: January 27, 2025
