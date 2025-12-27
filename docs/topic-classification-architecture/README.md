# Topic Classification Architecture Documentation

This folder contains all documentation related to the topic-based classification system re-architecture.

## 📚 Document Index

### 🎯 Core Implementation Documents

1. **TOPIC_CLASSIFICATION_IMPLEMENTATION.md**
   - Complete implementation plan
   - Code examples and architecture
   - File structure and data models
   - Step-by-step implementation guide

2. **DATABASE_MIGRATION_PLAN.md**
   - Database schema design
   - Many-to-many relationship structure
   - Migration scripts
   - SQLAlchemy models
   - Query examples

3. **NEXT_STEPS_ACTION_PLAN.md**
   - Actionable next steps
   - Implementation phases
   - Testing checklist
   - Dependencies

### 📖 Reference Guides

4. **TOPIC_DEFINITION_GUIDE.md**
   - Detailed explanation of topic fields
   - Best practices
   - Examples and use cases

5. **TOPIC_DEFINITION_QUICK_GUIDE.md**
   - One-page quick reference
   - Field explanations
   - Quick tips

### 📊 Templates & Examples

6. **topic_definitions_template.csv**
   - CSV template with 10 example topics
   - Ready to use format

7. **topic_definitions_template_blank.csv**
   - Blank CSV template
   - Fill with your topics

### 🔄 Current System Reference

8. **CLASSIFICATION_FLOW_CURRENT_SYSTEM.md**
   - Current LLM-based classification flow
   - Reference for understanding changes
   - Sentiment → Ministry → Issues flow

## 🚀 Quick Start

1. **Read First**: `TOPIC_CLASSIFICATION_IMPLEMENTATION.md` - Overview
2. **Database**: `DATABASE_MIGRATION_PLAN.md` - Schema design
3. **Action Plan**: `NEXT_STEPS_ACTION_PLAN.md` - What to do next
4. **Topic Definitions**: Use CSV templates to create topics

## 📋 Implementation Order

1. Create `config/master_topics.json` (use CSV templates)
2. Create owner configs (`president_config.json`, minister configs)
3. Generate topic embeddings
4. Implement `TopicClassifier`
5. Set up database schema
6. Modify existing classifiers
7. Migrate data
8. Update dashboards

## 🔑 Key Concepts

- **Topics**: Replace ministries as classification targets
- **Many-to-Many**: One mention can have multiple topics
- **Keyword + Embedding**: Fast, local classification (no LLM)
- **Database-Backed**: Issues stored in `topic_issues` table
- **Owner Configs**: President/ministers have topic lists

## 📝 Notes

- All documents are in Markdown format
- CSV templates can be converted to JSON
- Database migrations are SQL scripts
- Code examples are Python/SQLAlchemy

---

*Last Updated: December 2024*

