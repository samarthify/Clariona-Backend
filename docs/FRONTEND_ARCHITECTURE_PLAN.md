# Frontend Architecture Plan
## Governance Intelligence Platform - Clariona

**Created**: January 27, 2025  
**Status**: 📋 **MASTER PLAN**  
**Purpose**: Complete frontend architecture and implementation plan for Governance Intelligence Platform

---

## Executive Summary

This document outlines the complete frontend architecture for Clariona, a specialized Governance Intelligence Platform designed for government leadership (President, Ministers, CCC Directors, Analysts). The frontend must support:

- **Real-time intelligence dashboards** for national and ministerial views
- **4-level drilldown**: Nation → Issue → Category → Individual Posts
- **Role-based access** with tailored workflows
- **Automated briefings** and AI-generated summaries
- **Policy impact assessment** and early warning systems
- **Secure, compliant** architecture suitable for government deployment

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Technology Stack](#technology-stack)
3. [Application Structure](#application-structure)
4. [Core Modules](#core-modules)
5. [Role-Based Dashboards](#role-based-dashboards)
6. [Data Flow Integration](#data-flow-integration)
7. [UI/UX Design Principles](#uiux-design-principles)
8. [Security & Compliance](#security--compliance)
9. [Performance Requirements](#performance-requirements)
10. [Implementation Phases](#implementation-phases)
11. [Component Library](#component-library)
12. [API Integration](#api-integration)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Web App    │  │  Mobile App  │  │  Admin Panel │      │
│  │  (React/TS)  │  │  (React Nav) │  │  (React/TS)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │              │
│         └─────────────────┴──────────────────┘              │
│                            │                                │
│                    ┌───────▼────────┐                       │
│                    │  API Gateway    │                       │
│                    │  (AWS ALB)      │                       │
│                    └───────┬────────┘                       │
└────────────────────────────┼────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   Backend API     │
                    │  (FastAPI/Python)│
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
│   AWS (Cloud)   │  │  On-Premises   │  │   Database     │
│  - Ingestion    │  │  - LLM/Infer   │  │  - PostgreSQL  │
│  - Processing   │  │  - Sensitive    │  │  - Vector DB   │
│  - Dashboards   │  │  - Metadata    │  │  - Redis       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Frontend Deployment Model

**Hybrid Architecture Considerations**:
- **Web App**: Deployed on AWS (ECS/Fargate) for scalability
- **Static Assets**: Served via CloudFront CDN
- **API Calls**: Route through AWS ALB to backend
- **Real-time Updates**: WebSocket connections (via AWS API Gateway)
- **Authentication**: JWT tokens with role-based access
- **Data Residency**: Frontend doesn't store sensitive data (all via API)

---

## Technology Stack

### Core Framework

**Primary Stack**:
- **Framework**: React 18+ with TypeScript
- **State Management**: Redux Toolkit + RTK Query
- **Routing**: React Router v6
- **UI Library**: Material-UI (MUI) v5 or Ant Design
- **Charts**: Recharts or Chart.js
- **Maps**: Leaflet or Mapbox (for regional visualization)
- **Real-time**: Socket.io-client or WebSocket API
- **Forms**: React Hook Form + Zod validation
- **Date Handling**: date-fns or Day.js

### Supporting Libraries

- **HTTP Client**: Axios with interceptors
- **Code Splitting**: React.lazy + Suspense
- **Error Handling**: React Error Boundary
- **Logging**: Sentry (for production error tracking)
- **Testing**: Jest + React Testing Library + Playwright (E2E)
- **Build Tool**: Vite (faster than CRA)
- **Linting**: ESLint + Prettier
- **Type Safety**: TypeScript strict mode

### Mobile (Future Phase)

- **Framework**: React Native or Flutter
- **Priority**: Web-first, mobile later

---

## Application Structure

### Project Organization

```
frontend/
├── public/
│   ├── assets/
│   │   ├── images/
│   │   ├── icons/
│   │   └── fonts/
│   └── index.html
├── src/
│   ├── app/                    # App-level config
│   │   ├── store.ts            # Redux store
│   │   ├── router.tsx          # Route definitions
│   │   └── App.tsx             # Root component
│   ├── features/               # Feature-based modules
│   │   ├── dashboard/
│   │   ├── issues/
│   │   ├── alerts/
│   │   ├── sentiment/
│   │   ├── briefings/
│   │   ├── analytics/
│   │   └── admin/
│   ├── shared/                 # Shared components
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── types/
│   │   └── constants/
│   ├── api/                    # API layer
│   │   ├── endpoints.ts
│   │   ├── client.ts
│   │   └── websocket.ts
│   ├── auth/                   # Authentication
│   │   ├── login/
│   │   ├── guards/
│   │   └── hooks/
│   └── styles/                 # Global styles
│       ├── theme.ts
│       └── globals.css
├── tests/
├── .env.example
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

### Feature-Based Architecture

Each feature module is self-contained:

```
features/dashboard/
├── components/
│   ├── DashboardLayout.tsx
│   ├── MetricCard.tsx
│   ├── TrendChart.tsx
│   └── RegionalMap.tsx
├── hooks/
│   ├── useDashboardData.ts
│   └── useRealTimeUpdates.ts
├── services/
│   └── dashboardApi.ts
├── types/
│   └── dashboard.types.ts
└── index.ts
```

---

## Core Modules

### 1. Authentication & Authorization Module

**Purpose**: Secure role-based access control

**Components**:
- Login page (username/password + 2FA)
- Role-based route guards
- Session management
- Token refresh logic

**Roles**:
- `president` - Highest level access
- `ccc_director` - Crisis management access
- `minister` - Ministry-specific access
- `analyst` - Full access, no restrictions
- `viewer` - Read-only access

**Implementation**:
```typescript
// Role-based route guard
const ProtectedRoute = ({ role, children }) => {
  const { user } = useAuth();
  if (!hasPermission(user.role, role)) {
    return <Navigate to="/unauthorized" />;
  }
  return children;
};
```

---

### 2. Dashboard Module

**Purpose**: Central intelligence hub for each role

#### 2.1 National Dashboard (President/CCC Director)

**Key Metrics**:
- **National Sentiment Index** (0-100 scale)
- **Active Issues Count** (Critical/High/Medium)
- **Alert Count** (Unacknowledged)
- **Regional Heat Map** (36 states + FCT)
- **Top 5 Issues** (by priority)
- **Sentiment Trend** (7-day, 30-day)

**Layout**:
```
┌─────────────────────────────────────────────────────────┐
│  Header: Logo | User | Notifications | Settings        │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Sentiment│  │  Issues   │  │  Alerts  │  │ Regions ││
│  │  Index   │  │  Active   │  │  Pending │  │  Map    ││
│  │   65/100 │  │    23     │  │    5     │  │         ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
├─────────────────────────────────────────────────────────┤
│  Top Issues (Priority Sorted)                           │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Issue 1: Fuel Price Increase (Critical)             ││
│  │   📍 12 states | ⚠️ 1,234 mentions | 😡 -0.65      ││
│  │   [View Details] [Generate Briefing]                ││
│  ├─────────────────────────────────────────────────────┤│
│  │ Issue 2: Education Strike (High)                   ││
│  │   📍 8 states | ⚠️ 856 mentions | 😟 -0.42          ││
│  │   [View Details] [Generate Briefing]                ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  Sentiment Trends (7-Day)                               │
│  [Line Chart: Sentiment Index over time]                │
├─────────────────────────────────────────────────────────┤
│  Regional Distribution                                   │
│  [Map: 36 states + FCT with color-coded sentiment]     │
└─────────────────────────────────────────────────────────┘
```

#### 2.2 Ministerial Dashboard

**Key Metrics**:
- **Ministry-Specific Sentiment** (for their MDA)
- **Issues in Their Domain** (filtered by topic)
- **Policy Impact Score** (if applicable)
- **Top Concerns** (from public mentions)
- **Response Rate** (alerts acknowledged/closed)

**Layout**: Similar to national, but filtered by ministry topics

#### 2.3 Analyst Dashboard

**Key Metrics**:
- **All Issues** (no filtering)
- **Processing Queue** (mentions pending classification)
- **Alert Triage** (unassigned alerts)
- **Data Quality Metrics** (duplicates, errors)
- **System Health** (API latency, processing rate)

---

### 3. Issues Module

**Purpose**: Detailed issue tracking and management

**Components**:
- **Issues List View** (table with filters)
- **Issue Detail View** (drilldown)
- **Issue Timeline** (mentions over time)
- **Issue Sentiment Breakdown** (emotion distribution)
- **Issue Priority Calculator** (shows score breakdown)
- **Issue Actions** (merge, split, archive, escalate)

**Issue Detail View**:
```
┌─────────────────────────────────────────────────────────┐
│  Issue: Fuel Price Increase                             │
│  Priority: Critical (Score: 87/100)                      │
│  Status: Active | Started: 2 hours ago                   │
├─────────────────────────────────────────────────────────┤
│  Metrics                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Mentions │  │ Velocity │  │ Sentiment│  │ Regions ││
│  │  1,234   │  │  +300/hr │  │  -0.65   │  │   12    ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
├─────────────────────────────────────────────────────────┤
│  Priority Score Breakdown                                │
│  • Volume: 25/100 (W1: 0.2)                             │
│  • Velocity: 30/100 (W2: 0.25)                          │
│  • Sentiment Severity: 20/100 (W3: 0.2)                 │
│  • Influence: 15/100 (W4: 0.15)                         │
│  • Geographic Spread: 10/100 (W5: 0.1)                 │
│  • Policy Sensitivity: 12/100 (W6: 0.1)                 │
├─────────────────────────────────────────────────────────┤
│  Sentiment Distribution                                  │
│  [Pie Chart: Positive 10% | Negative 80% | Neutral 10%] │
│  [Emotion Chart: Anger 60% | Fear 20% | Disgust 20%]   │
├─────────────────────────────────────────────────────────┤
│  Regional Spread                                        │
│  [Map: States highlighted by mention count]             │
├─────────────────────────────────────────────────────────┤
│  Top Keywords                                           │
│  fuel, price, increase, subsidy, NNPC, petrol          │
├─────────────────────────────────────────────────────────┤
│  Recent Mentions (Sample)                                │
│  ┌─────────────────────────────────────────────────────┐│
│  │ "Fuel prices are too high, government must act"     ││
│  │   📍 Lagos | 🕐 15 min ago | 😡 Negative (-0.8)    ││
│  │   [View Full]                                        ││
│  ├─────────────────────────────────────────────────────┤│
│  │ "Why is petrol so expensive now?"                   ││
│  │   📍 Abuja | 🕐 20 min ago | 😟 Negative (-0.6)    ││
│  │   [View Full]                                        ││
│  └─────────────────────────────────────────────────────┘│
│  [Load More] [Export Data]                              │
├─────────────────────────────────────────────────────────┤
│  Actions                                                │
│  [Generate Briefing] [Create Alert] [Merge Issue]       │
│  [Archive] [Escalate]                                   │
└─────────────────────────────────────────────────────────┘
```

**4-Level Drilldown**:
1. **Nation Level**: All issues aggregated
2. **Issue Level**: Single issue with all mentions
3. **Category Level**: Mentions grouped by topic/sub-topic
4. **Post Level**: Individual mention details

---

### 4. Alerts Module

**Purpose**: Real-time alert management and escalation

**Components**:
- **Alert Stream** (real-time feed)
- **Alert Detail View** (trigger reasons, SLA timer)
- **Alert Actions** (acknowledge, escalate, close)
- **Alert Filters** (by priority, type, status)
- **SLA Monitoring** (time remaining, missed alerts)

**Alert Stream View**:
```
┌─────────────────────────────────────────────────────────┐
│  Alerts (5 Unacknowledged)                              │
│  [Filter: All | Critical | High | Medium]               │
├─────────────────────────────────────────────────────────┤
│  🔴 CRITICAL - Fuel Price Spike                         │
│     Issue: Fuel Price Increase                          │
│     Trigger: Volume Spike (6× baseline)                │
│     SLA: 15 min remaining ⏰                            │
│     [Acknowledge] [View Issue] [Escalate]               │
├─────────────────────────────────────────────────────────┤
│  🟠 HIGH - Sentiment Shift: Education                   │
│     Issue: ASUU Strike                                  │
│     Trigger: Negative sentiment 22% → 48%              │
│     SLA: 1h 30min remaining ⏰                          │
│     [Acknowledge] [View Issue]                          │
├─────────────────────────────────────────────────────────┤
│  🟡 MEDIUM - Regional Escalation                        │
│     Issue: Transport Fare Increase                     │
│     Trigger: Spread to 5 states                        │
│     SLA: 4h remaining ⏰                                │
│     [Acknowledge] [View Issue]                          │
└─────────────────────────────────────────────────────────┘
```

**Alert Detail View**:
- Trigger reasons (with evidence)
- Linked issue details
- SLA countdown timer
- Assignment history
- Action log
- Escalation path

---

### 5. Sentiment Module

**Purpose**: Sentiment analytics and trends

**Components**:
- **Sentiment Overview** (national, by topic, by issue)
- **Sentiment Trends** (time-series charts)
- **Emotion Breakdown** (8 emotions: anger, fear, trust, etc.)
- **Topic-Adjusted Sentiment** (normalized by baseline)
- **Sentiment Comparison** (period-over-period)
- **Sentiment Heatmap** (by region, by topic)

**Sentiment Dashboard**:
```
┌─────────────────────────────────────────────────────────┐
│  National Sentiment Overview                             │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Sentiment Index: 65/100 (Neutral-Positive)          ││
│  │ Trend: ↑ Improving (+5 points in 7 days)            ││
│  │ [7D] [30D] [90D] [Custom Range]                      ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  Sentiment Distribution                                 │
│  [Stacked Bar: Positive | Neutral | Negative over time] │
├─────────────────────────────────────────────────────────┤
│  Emotion Breakdown                                      │
│  [Horizontal Bar: Anger 40% | Fear 25% | Trust 20%...]  │
├─────────────────────────────────────────────────────────┤
│  Sentiment by Topic                                     │
│  [Table: Topic | Sentiment Index | Trend | Mentions]    │
│  • Fuel Pricing: 35/100 (↓ Deteriorating) - 1,234       │
│  • Education: 42/100 (→ Stable) - 856                   │
│  • Health: 68/100 (↑ Improving) - 432                   │
├─────────────────────────────────────────────────────────┤
│  Regional Sentiment                                     │
│  [Map: States color-coded by sentiment index]           │
└─────────────────────────────────────────────────────────┘
```

---

### 6. Briefings Module

**Purpose**: AI-generated executive briefings

**Components**:
- **Briefing Generator** (on-demand for issues/alerts)
- **Briefing Templates** (President, Minister, CCC)
- **Briefing History** (past briefings)
- **Briefing Export** (PDF, Word, Email)

**Briefing Structure**:
1. **Executive Summary** (2-3 sentences)
2. **Key Issues** (top 3-5 by priority)
3. **Sentiment Overview** (national + trends)
4. **Regional Highlights** (state-level insights)
5. **Recommended Actions** (AI-suggested)
6. **Supporting Data** (charts, tables)

**Briefing Generator**:
```
┌─────────────────────────────────────────────────────────┐
│  Generate Briefing                                       │
│  ┌─────────────────────────────────────────────────────┐│
│  │ Recipient: [President ▼]                            │
│  │ Time Range: [Last 24 hours ▼]                       │
│  │ Include: [✓ Issues] [✓ Sentiment] [✓ Alerts]       │
│  │         [✓ Regional] [✓ Recommendations]            │
│  │                                                      │
│  │ [Generate Briefing] [Use Template]                  │
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  Generated Briefing (Preview)                            │
│  ┌─────────────────────────────────────────────────────┐│
│  │ EXECUTIVE SUMMARY                                    │
│  │ National sentiment remains neutral-positive (65/100)│
│  │ with 23 active issues requiring attention...         │
│  │                                                      │
│  │ KEY ISSUES                                           │
│  │ 1. Fuel Price Increase (Critical)                    │
│  │    ...                                               │
│  │                                                      │
│  │ [Edit] [Export PDF] [Email] [Save]                  │
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

---

### 7. Analytics Module

**Purpose**: Advanced analytics and reporting

**Components**:
- **Custom Reports** (build your own)
- **Policy Impact Assessment** (before/after analysis)
- **Trend Analysis** (predictive insights)
- **Comparative Analysis** (topic vs topic, period vs period)
- **Export Tools** (CSV, PDF, Excel)

---

### 8. Admin Module

**Purpose**: System configuration and management

**Components**:
- **User Management** (CRUD users, assign roles)
- **Topic Configuration** (manage topics, keywords)
- **Alert Thresholds** (configure trigger conditions)
- **System Settings** (API keys, integrations)
- **Audit Logs** (user actions, system events)
- **Data Management** (backup, export, purge)

---

## Role-Based Dashboards

### President Dashboard

**Access Level**: Highest (all data, all regions)

**Key Features**:
- National sentiment overview
- Critical issues only (priority ≥ 80)
- Critical alerts only
- Regional heatmap (36 states + FCT)
- Executive briefings (auto-generated daily)
- Policy impact summaries

**Layout Priority**:
1. National Sentiment Index (prominent)
2. Top 5 Critical Issues
3. Critical Alerts (if any)
4. Regional Distribution
5. Sentiment Trends

**Restrictions**:
- No access to analyst tools
- No access to system configuration
- Read-only on most data (can generate briefings)

---

### CCC Director Dashboard

**Access Level**: Crisis management (all issues, all alerts)

**Key Features**:
- All issues (Critical + High priority)
- All alerts (Critical + High)
- Real-time alert stream
- Regional crisis map
- Issue escalation workflow
- SitRep generation

**Layout Priority**:
1. Alert Stream (real-time)
2. Active Issues (Critical + High)
3. Regional Crisis Map
4. Sentiment Volatility Indicators
5. Issue Priority Breakdown

---

### Minister Dashboard

**Access Level**: Ministry-specific (filtered by topics)

**Key Features**:
- Ministry-specific sentiment
- Issues in their domain only
- Policy impact assessment
- Public concerns (top mentions)
- Response tracking (alerts closed)
- Ministry briefings

**Layout Priority**:
1. Ministry Sentiment Index
2. Active Issues (their domain)
3. Top Public Concerns
4. Policy Impact Score
5. Response Metrics

**Filtering**:
- Automatically filtered by ministry topics
- Can view related topics (cross-ministry issues)
- Cannot see other ministries' exclusive data

---

### Analyst Dashboard

**Access Level**: Full access (all data, all tools)

**Key Features**:
- All issues (no filtering)
- All alerts (triage view)
- Processing queue (pending mentions)
- Data quality metrics
- Issue management tools (merge, split, archive)
- System health monitoring

**Layout Priority**:
1. Processing Queue
2. Alert Triage
3. All Issues (with filters)
4. Data Quality Dashboard
5. System Health

---

## Data Flow Integration

### Backend Data Flow → Frontend Mapping

```
Backend Flow:          Frontend Display:
─────────────────────────────────────────
Mentions (Raw)    →    Mentions List (Analyst View)
    ↓
Topics (Classification) → Topic Tags, Topic Filters
    ↓
Issues (Clustered) → Issues Dashboard, Issue Detail
    ↓
Issue Priority → Priority Bands, Alert Triggers
    ↓
Alerts (Decisions) → Alert Stream, Alert Detail
    ↓
Sentiment Aggregation → Sentiment Dashboard, Trends
    ↓
Briefings (AI) → Briefing Generator, Briefing History
```

### Real-Time Updates

**WebSocket Integration**:
```typescript
// Real-time alert stream
const useRealTimeAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  
  useEffect(() => {
    const ws = new WebSocket('wss://api.clariona.gov.ng/alerts');
    
    ws.onmessage = (event) => {
      const alert = JSON.parse(event.data);
      setAlerts(prev => [alert, ...prev]);
    };
    
    return () => ws.close();
  }, []);
  
  return alerts;
};
```

**Polling Fallback**:
- If WebSocket fails, fall back to polling (every 5-10 seconds)
- Show connection status indicator

---

## UI/UX Design Principles

### Design System

**Color Palette**:
- **Primary**: Government blue (#003366) - Trust, authority
- **Secondary**: Green (#00A651) - Positive sentiment
- **Warning**: Orange (#FF6B35) - Medium priority
- **Critical**: Red (#DC143C) - High priority alerts
- **Neutral**: Gray (#6C757D) - Neutral sentiment
- **Background**: Light gray (#F5F5F5) - Clean, professional

**Typography**:
- **Headings**: Inter or Roboto (clean, modern)
- **Body**: System font stack (performance)
- **Monospace**: For data/code (Courier New)

**Components**:
- **Cards**: Elevated, rounded corners, subtle shadows
- **Tables**: Sortable, filterable, paginated
- **Charts**: Interactive (tooltips, zoom, export)
- **Forms**: Clear labels, validation feedback
- **Buttons**: Primary (solid), Secondary (outlined), Danger (red)

### Accessibility

- **WCAG 2.1 AA Compliance**:
  - Color contrast ratios (4.5:1 minimum)
  - Keyboard navigation (all interactive elements)
  - Screen reader support (ARIA labels)
  - Focus indicators (visible focus states)

### Responsive Design

**Breakpoints**:
- **Mobile**: < 768px (single column, stacked)
- **Tablet**: 768px - 1024px (2 columns)
- **Desktop**: > 1024px (full layout)
- **Large Desktop**: > 1440px (expanded layout)

**Mobile Considerations**:
- Simplified dashboards (key metrics only)
- Bottom navigation (instead of sidebar)
- Swipe gestures for navigation
- Touch-friendly targets (44×44px minimum)

---

## Security & Compliance

### Authentication

**Implementation**:
- JWT tokens (access + refresh)
- Token stored in httpOnly cookies (XSS protection)
- Automatic token refresh (before expiry)
- Session timeout (30 minutes inactivity)

**2FA**:
- TOTP (Time-based One-Time Password)
- SMS backup (optional)
- Recovery codes

### Authorization

**Role-Based Access Control (RBAC)**:
```typescript
// Permission matrix
const permissions = {
  president: ['view:national', 'view:all_issues', 'generate:briefings'],
  ccc_director: ['view:all_issues', 'view:all_alerts', 'manage:escalations'],
  minister: ['view:ministry_issues', 'view:ministry_sentiment', 'acknowledge:alerts'],
  analyst: ['view:all', 'manage:issues', 'manage:alerts', 'admin:system'],
};
```

### Data Security

**Frontend Security**:
- No sensitive data in localStorage (use httpOnly cookies)
- API keys in environment variables (not in code)
- HTTPS only (no HTTP)
- Content Security Policy (CSP) headers
- XSS protection (sanitize user inputs)

### Compliance

**Requirements**:
- **GDPR**: User data export, deletion, consent
- **ISO 27001**: Security controls
- **NDPA 2023** (Nigeria): Data protection compliance
- **Audit Logging**: All user actions logged

---

## Performance Requirements

### Target Metrics

- **Initial Load**: < 3 seconds (First Contentful Paint)
- **Time to Interactive**: < 5 seconds
- **API Response**: < 500ms (p95)
- **Real-time Updates**: < 1 second latency
- **Chart Rendering**: < 100ms for 1000 data points

### Optimization Strategies

**Code Splitting**:
```typescript
// Lazy load routes
const Dashboard = lazy(() => import('./features/dashboard'));
const Issues = lazy(() => import('./features/issues'));

// Lazy load heavy components
const Chart = lazy(() => import('./components/Chart'));
```

**Caching**:
- API responses cached (RTK Query)
- Static assets cached (CDN)
- Browser caching (Cache-Control headers)

**Bundle Size**:
- Target: < 500KB initial bundle (gzipped)
- Tree shaking (remove unused code)
- Dynamic imports (load on demand)

**Image Optimization**:
- WebP format (with fallback)
- Lazy loading images
- Responsive images (srcset)

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)

**Goals**: Setup, authentication, basic layout

**Tasks**:
- [ ] Project setup (Vite + React + TypeScript)
- [ ] Design system (theme, colors, typography)
- [ ] Authentication module (login, guards, roles)
- [ ] Layout components (header, sidebar, footer)
- [ ] Routing setup (protected routes)
- [ ] API client setup (Axios, interceptors)
- [ ] State management (Redux store)

**Deliverable**: Working authentication + basic layout

---

### Phase 2: Core Dashboards (Weeks 3-4)

**Goals**: National, Ministerial, Analyst dashboards

**Tasks**:
- [ ] National Dashboard (President/CCC)
  - [ ] Metric cards (sentiment, issues, alerts)
  - [ ] Top issues list
  - [ ] Sentiment trend chart
  - [ ] Regional map
- [ ] Ministerial Dashboard (filtered by topics)
- [ ] Analyst Dashboard (full access)
- [ ] Real-time updates (WebSocket integration)

**Deliverable**: All role-based dashboards functional

---

### Phase 3: Issues Module (Weeks 5-6)

**Goals**: Complete issue tracking and management

**Tasks**:
- [ ] Issues list view (table, filters, sorting)
- [ ] Issue detail view (4-level drilldown)
- [ ] Issue priority calculator (score breakdown)
- [ ] Issue actions (merge, split, archive)
- [ ] Issue timeline (mentions over time)
- [ ] Sentiment breakdown (emotion charts)

**Deliverable**: Full issue management workflow

---

### Phase 4: Alerts Module (Weeks 7-8)

**Goals**: Real-time alert management

**Tasks**:
- [ ] Alert stream (real-time feed)
- [ ] Alert detail view (trigger reasons, SLA)
- [ ] Alert actions (acknowledge, escalate, close)
- [ ] Alert filters (priority, type, status)
- [ ] SLA monitoring (countdown timers)
- [ ] Alert assignment logic

**Deliverable**: Complete alert management system

---

### Phase 5: Sentiment & Analytics (Weeks 9-10)

**Goals**: Sentiment dashboards and analytics

**Tasks**:
- [ ] Sentiment overview (national, topic, issue)
- [ ] Sentiment trends (time-series charts)
- [ ] Emotion breakdown (8 emotions)
- [ ] Topic-adjusted sentiment (normalized)
- [ ] Regional sentiment map
- [ ] Custom reports builder

**Deliverable**: Comprehensive sentiment analytics

---

### Phase 6: Briefings & Admin (Weeks 11-12)

**Goals**: AI briefings and admin tools

**Tasks**:
- [ ] Briefing generator (on-demand)
- [ ] Briefing templates (role-based)
- [ ] Briefing export (PDF, Word, Email)
- [ ] Admin panel (user management)
- [ ] Topic configuration UI
- [ ] Alert threshold configuration
- [ ] System settings
- [ ] Audit logs viewer

**Deliverable**: Complete briefing system + admin tools

---

### Phase 7: Polish & Testing (Weeks 13-14)

**Goals**: Performance, accessibility, testing

**Tasks**:
- [ ] Performance optimization (code splitting, caching)
- [ ] Accessibility audit (WCAG 2.1 AA)
- [ ] Responsive design (mobile, tablet)
- [ ] Unit tests (Jest, React Testing Library)
- [ ] E2E tests (Playwright)
- [ ] Error handling (error boundaries, fallbacks)
- [ ] Documentation (user guides, API docs)

**Deliverable**: Production-ready frontend

---

## Component Library

### Reusable Components

**Data Display**:
- `MetricCard` - Key metric with trend indicator
- `TrendChart` - Time-series line/area chart
- `SentimentGauge` - Sentiment index (0-100) with color coding
- `PriorityBadge` - Issue/alert priority badge (Critical/High/Medium/Low)
- `EmotionChart` - Horizontal bar chart for emotions
- `RegionalMap` - Interactive map with state-level data

**Navigation**:
- `Sidebar` - Role-based navigation menu
- `Breadcrumbs` - Navigation breadcrumbs
- `TabNavigation` - Tab-based navigation

**Forms**:
- `FilterPanel` - Advanced filtering UI
- `DateRangePicker` - Date range selection
- `SearchInput` - Search with autocomplete
- `SelectDropdown` - Multi-select dropdown

**Feedback**:
- `AlertToast` - Toast notifications
- `LoadingSpinner` - Loading states
- `EmptyState` - Empty state messages
- `ErrorBoundary` - Error handling

**Tables**:
- `DataTable` - Sortable, filterable, paginated table
- `IssueTable` - Specialized issue table
- `AlertTable` - Specialized alert table

---

## API Integration

### ⚠️ Important: Database Access Architecture

**The frontend NEVER directly queries the database.**

All database access goes through the **Backend API layer**:
- Frontend makes HTTP requests to backend API endpoints
- Backend API queries the database using SQLAlchemy ORM
- Backend API returns JSON responses to frontend

**See**: [FRONTEND_DATABASE_QUERY_ARCHITECTURE.md](./FRONTEND_DATABASE_QUERY_ARCHITECTURE.md) for complete data flow details.

### API Endpoints Structure

**Base URL**: `https://api.clariona.gov.ng/v1`

**Endpoints**:
```
GET  /auth/me                    # Current user
POST /auth/login                 # Login
POST /auth/refresh               # Refresh token

GET  /dashboard/national          # National dashboard data
GET  /dashboard/ministry/:id      # Ministry dashboard
GET  /dashboard/analyst           # Analyst dashboard

GET  /issues                     # List issues (with filters)
GET  /issues/:id                 # Issue detail
POST /issues/:id/merge            # Merge issues
POST /issues/:id/split            # Split issue
POST /issues/:id/archive          # Archive issue

GET  /alerts                     # List alerts
GET  /alerts/:id                 # Alert detail
POST /alerts/:id/acknowledge      # Acknowledge alert
POST /alerts/:id/escalate         # Escalate alert
POST /alerts/:id/close            # Close alert

GET  /sentiment/national          # National sentiment
GET  /sentiment/topic/:key        # Topic sentiment
GET  /sentiment/issue/:id         # Issue sentiment
GET  /sentiment/trends            # Sentiment trends

POST /briefings/generate          # Generate briefing
GET  /briefings/:id               # Get briefing
GET  /briefings                   # List briefings

GET  /topics                      # List topics
GET  /regions                     # List regions (states)

GET  /admin/users                 # User management
GET  /admin/audit-logs            # Audit logs
```

### API Client Implementation

```typescript
// API client with interceptors
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 30000,
});

// Request interceptor (add token)
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor (handle errors, refresh token)
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Refresh token logic
    }
    return Promise.reject(error);
  }
);
```

### RTK Query Integration

```typescript
// API slice with RTK Query
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const api = createApi({
  baseQuery: fetchBaseQuery({
    baseUrl: '/api/v1',
    prepareHeaders: (headers, { getState }) => {
      const token = selectToken(getState());
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  endpoints: (builder) => ({
    getNationalDashboard: builder.query<DashboardData, void>({
      query: () => '/dashboard/national',
    }),
    getIssues: builder.query<Issue[], IssueFilters>({
      query: (filters) => ({
        url: '/issues',
        params: filters,
      }),
    }),
    // ... more endpoints
  }),
});
```

---

## Testing Strategy

### Unit Tests

**Coverage Target**: 80%+

**Tools**:
- Jest (test runner)
- React Testing Library (component testing)
- MSW (Mock Service Worker for API mocking)

**Test Areas**:
- Components (rendering, interactions)
- Hooks (custom hooks logic)
- Utils (helper functions)
- Redux slices (state management)

### Integration Tests

**Tools**:
- React Testing Library (component integration)
- MSW (API mocking)

**Test Areas**:
- User flows (login → dashboard → issue detail)
- API integration (data fetching, error handling)
- Form submissions
- Real-time updates

### E2E Tests

**Tools**:
- Playwright (browser automation)

**Test Scenarios**:
- Complete user journeys (President, Minister, Analyst)
- Alert acknowledgment workflow
- Issue management workflow
- Briefing generation workflow

---

## Deployment

### Build Process

```bash
# Development
npm run dev

# Production build
npm run build

# Preview production build
npm run preview

# Run tests
npm run test
npm run test:e2e
```

### Deployment Pipeline

**CI/CD** (GitHub Actions):
1. **Lint & Test**: Run ESLint, TypeScript check, unit tests
2. **Build**: Create production bundle
3. **E2E Tests**: Run Playwright tests
4. **Deploy**: Deploy to AWS (ECS/Fargate)
5. **CDN**: Invalidate CloudFront cache

**Environment Variables**:
```env
VITE_API_URL=https://api.clariona.gov.ng/v1
VITE_WS_URL=wss://api.clariona.gov.ng
VITE_ENV=production
VITE_SENTRY_DSN=...
```

---

## Documentation Requirements

### User Documentation

- **User Guides**: Per role (President, Minister, Analyst)
- **Video Tutorials**: Key workflows
- **FAQ**: Common questions
- **Release Notes**: Per version

### Developer Documentation

- **Component Library**: Storybook
- **API Documentation**: OpenAPI/Swagger
- **Architecture Docs**: This document
- **Contributing Guide**: How to contribute

---

## Success Metrics

### User Engagement

- **Daily Active Users**: Target 80% of licensed users
- **Session Duration**: Average 15+ minutes
- **Feature Adoption**: 70%+ users use core features

### Performance

- **Page Load Time**: < 3 seconds (p95)
- **API Response Time**: < 500ms (p95)
- **Error Rate**: < 0.1%

### Business Impact

- **Alert Response Time**: 50% reduction
- **Briefing Generation Time**: < 2 minutes
- **User Satisfaction**: 4.5/5.0

---

## Next Steps

1. **Review & Approve**: This architecture plan
2. **Design Mockups**: Create Figma designs for key screens
3. **Setup Project**: Initialize React + TypeScript project
4. **Begin Phase 1**: Foundation (authentication, layout)
5. **Iterate**: Weekly sprints, bi-weekly demos

---

**Status**: 📋 **MASTER PLAN COMPLETE**  
**Last Updated**: January 27, 2025  
**Next Review**: After Phase 1 completion





