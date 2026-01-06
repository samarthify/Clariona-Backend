from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, Index, Text, Boolean, ForeignKey, UniqueConstraint, JSON, UUID, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from typing import TYPE_CHECKING
import datetime
import uuid

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase
    Base: type[DeclarativeBase]
else:
    # Import Base from database.py
    from .database import Base

# Load string length constants from ConfigManager
def _get_string_lengths():
    """Get string length constants from ConfigManager with fallback defaults."""
    try:
        from config.config_manager import ConfigManager
        config = ConfigManager()
        return {
            'short': config.get_int("models.string_lengths.short", 50),
            'medium': config.get_int("models.string_lengths.medium", 100),
            'long': config.get_int("models.string_lengths.long", 200),
            'very_long': config.get_int("models.string_lengths.very_long", 500),
            'password_hash': config.get_int("models.string_lengths.password_hash", 255),
            'config_key': config.get_int("models.string_lengths.config_key", 255)
        }
    except Exception:
        # Fallback to defaults if ConfigManager not available
        return {
            'short': 50,
            'medium': 100,
            'long': 200,
            'very_long': 500,
            'password_hash': 255,
            'config_key': 255
        }

# Load embedding model name from ConfigManager
def _get_embedding_model():
    """Get embedding model name from ConfigManager with fallback default."""
    try:
        from config.config_manager import ConfigManager
        config = ConfigManager()
        return config.get("models.embedding_model", "text-embedding-3-small")
    except Exception:
        return "text-embedding-3-small"

# Module-level constants
STRING_LENGTHS = _get_string_lengths()
EMBEDDING_MODEL = _get_embedding_model()

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String(STRING_LENGTHS['medium']), nullable=True, index=True)
    password_hash = Column(String(STRING_LENGTHS['password_hash']), nullable=True)
    role = Column(String(STRING_LENGTHS['short']), nullable=True)
    ministry = Column(String(STRING_LENGTHS['short']), nullable=True)
    name = Column(String(STRING_LENGTHS['long']), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, default=False)
    api_calls_count = Column(Integer, default=0)
    data_entries_count = Column(Integer, default=0)

    # Relationships
    sentiment_data = relationship("SentimentData", back_populates="user")
    email_configurations = relationship("EmailConfiguration", back_populates="user")
    target_configurations = relationship("TargetIndividualConfiguration", back_populates="user")

class SentimentData(Base):
    __tablename__ = 'sentiment_data'

    # Internal fields
    entry_id = Column(Integer, primary_key=True, autoincrement=True)
    run_timestamp = Column(DateTime(timezone=False), nullable=False, index=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    user = relationship("User", back_populates="sentiment_data")
    embedding = relationship("SentimentEmbedding", back_populates="sentiment_data", uselist=False)

    # Fields from CSV
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    published_date = Column(DateTime(timezone=False), nullable=True)
    source = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    query = Column(String, nullable=True)
    language = Column(String, nullable=True)
    platform = Column(String, nullable=True, index=True)
    date = Column(DateTime(timezone=False), nullable=True) # Specific 'date' column from CSV
    text = Column(Text, nullable=True) # Using Text for potentially long content
    file_source = Column(String, nullable=True)
    original_id = Column(String, nullable=True) # Renamed from 'id' in CSV to avoid conflict
    published_at = Column(DateTime(timezone=False), nullable=True) # Specific 'published_at' column
    source_type = Column(String, nullable=True)
    country = Column(String, nullable=True)
    favorite = Column(Boolean, nullable=True)
    tone = Column(String, nullable=True)
    source_name = Column(String, nullable=True)
    parent_url = Column(String, nullable=True)
    parent_id = Column(String, nullable=True) # Assuming string ID
    direct_reach = Column(Integer, nullable=True)
    cumulative_reach = Column(Integer, nullable=True)
    domain_reach = Column(Integer, nullable=True)
    tags = Column(String, nullable=True) # Storing tags as a string, consider JSON if needed
    alert_name = Column(String, nullable=True)
    type = Column(String, nullable=True) # 'type' field from CSV
    post_id = Column(String, nullable=True)
    retweets = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    user_location = Column(String, nullable=True)
    comments = Column(Integer, nullable=True)
    user_name = Column(String, nullable=True)
    user_handle = Column(String, nullable=True)
    user_avatar = Column(String, nullable=True) # URL to avatar
    sentiment_label = Column(String, nullable=True, index=True) # Keep existing sentiment fields
    sentiment_score = Column(Float, nullable=True)
    sentiment_justification = Column(Text, nullable=True) # Field for ChatGPT justification
    
    # Enhanced sentiment fields (Week 3)
    emotion_label = Column(String(50), nullable=True)
    emotion_score = Column(Float, nullable=True)
    emotion_distribution = Column(JSONB, nullable=True)
    influence_weight = Column(Float, nullable=True, default=1.0)
    confidence_weight = Column(Float, nullable=True)
    
    # Processing status fields (for safe concurrent processing)
    processing_status = Column(String(20), nullable=True, default='pending', index=True)  # pending, processing, completed, failed
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Enhanced location classification fields
    location_label = Column(String, nullable=True)
    location_confidence = Column(Float, nullable=True)
    
    # Issue mapping fields
    issue_label = Column(String, nullable=True)
    issue_slug = Column(String, nullable=True)
    issue_confidence = Column(Float, nullable=True)
    issue_keywords = Column(JSON, nullable=True)
    ministry_hint = Column(String(STRING_LENGTHS['short']), nullable=True)

    # Optional: Add an index for faster querying by run_timestamp and platform
    __table_args__ = (
        Index('ix_sentiment_data_run_timestamp', 'run_timestamp'),
        Index('ix_sentiment_data_platform', 'platform'),
        # Add more indices if needed for frequent query patterns
    )

    def to_dict(self):
        # Helper to convert model instance to dictionary
        return {
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "url": self.url,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "source": self.source,
            "source_url": self.source_url,
            "query": self.query,
            "language": self.language,
            "platform": self.platform,
            "date": self.date.isoformat() if self.date else None,
            "text": self.text,
            "file_source": self.file_source,
            "id": self.original_id, # Map back to 'id' for consistency if needed elsewhere
            "alert_id": self.alert_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "source_type": self.source_type,
            "country": self.country,
            "favorite": self.favorite,
            "tone": self.tone,
            "source_name": self.source_name,
            "parent_url": self.parent_url,
            "parent_id": self.parent_id,
            "children": self.children,
            "direct_reach": self.direct_reach,
            "cumulative_reach": self.cumulative_reach,
            "domain_reach": self.domain_reach,
            "tags": self.tags,
            "score": self.score,
            "alert_name": self.alert_name,
            "type": self.type,
            "post_id": self.post_id,
            "retweets": self.retweets,
            "likes": self.likes,
            "user_location": self.user_location,
            "comments": self.comments,
            "user_name": self.user_name,
            "user_handle": self.user_handle,
            "user_avatar": self.user_avatar,
            "sentiment_label": self.sentiment_label,
            "sentiment_score": self.sentiment_score,
            "sentiment_justification": self.sentiment_justification,
            "location_label": self.location_label,
            "location_confidence": self.location_confidence,
            "issue_label": self.issue_label,
            "issue_slug": self.issue_slug,
            "issue_confidence": self.issue_confidence,
            "issue_keywords": self.issue_keywords,
            "ministry_hint": self.ministry_hint,
            # Optionally include internal fields
            # "entry_id": self.entry_id,
            # "run_timestamp": self.run_timestamp.isoformat(),
            # "created_at": self.created_at.isoformat()
        }

# Example usage (not needed in models.py itself):
# record = SentimentData(run_timestamp=datetime.datetime.now(), original_id='xyz', text='Test', ...) 

# New Models for Configuration Management

class EmailConfiguration(Base):
    __tablename__ = 'email_configurations'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    user = relationship("User", back_populates="email_configurations")
    provider = Column(String, nullable=False)
    smtp_server = Column(String, nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    recipients = Column(JSON, nullable=True)
    notify_on_collection = Column(Boolean, default=False, nullable=False)
    notify_on_processing = Column(Boolean, default=False, nullable=False)
    notify_on_analysis = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TargetIndividualConfiguration(Base):
    __tablename__ = 'target_individual_configurations'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True)
    user = relationship("User", back_populates="target_configurations")
    individual_name = Column(String, nullable=False)
    # Storing list of strings as JSON
    query_variations = Column(JSON, nullable=False) 
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 

# New model for user system usage logs
class UserSystemUsage(Base):
    __tablename__ = 'user_system_usage'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    execution_time_ms = Column(Integer, nullable=True)
    data_size = Column(Integer, nullable=True)  # Size of data processed in bytes
    status_code = Column(Integer, nullable=True)
    is_error = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    
    # Relationship with User
    user = relationship("User")

# Model for sentiment embeddings
class SentimentEmbedding(Base):
    __tablename__ = 'sentiment_embeddings'
    
    entry_id = Column(Integer, ForeignKey('sentiment_data.entry_id'), primary_key=True)
    embedding = Column(JSON, nullable=True)
    embedding_model = Column(String(STRING_LENGTHS['short']), nullable=True, default=EMBEDDING_MODEL)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    
    # Relationship with SentimentData
    sentiment_data = relationship("SentimentData", back_populates="embedding")

# ============================================
# Topic-Based Classification Models
# ============================================

class Topic(Base):
    """Master topics table for topic-based classification."""
    __tablename__ = 'topics'
    
    topic_key = Column(String(STRING_LENGTHS['medium']), primary_key=True)
    topic_name = Column(String(STRING_LENGTHS['long']), nullable=False)
    description = Column(Text)
    category = Column(String(STRING_LENGTHS['short']))
    keywords: list[str] = Column(ARRAY(Text))  # PostgreSQL array, fallback to JSON if needed (backward compatibility)
    keyword_groups = Column(JSONB)  # JSONB for AND/OR keyword logic
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    issues = relationship("TopicIssue", back_populates="topic", foreign_keys="TopicIssue.topic_key", cascade="all, delete-orphan")
    primary_issues = relationship("TopicIssue", foreign_keys="TopicIssue.primary_topic_key")
    mention_classifications = relationship("MentionTopic", back_populates="topic")
    issue_links = relationship("TopicIssueLink", back_populates="topic", cascade="all, delete-orphan")
    sentiment_baseline = relationship("TopicSentimentBaseline", back_populates="topic", uselist=False)

class TopicIssue(Base):
    """Enhanced issues per topic (clustering-based, with lifecycle and sentiment)."""
    __tablename__ = 'topic_issues'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_slug = Column(String(STRING_LENGTHS['long']), nullable=False, unique=True)  # Globally unique
    issue_label = Column(String(STRING_LENGTHS['very_long']), nullable=False)
    issue_title = Column(String(STRING_LENGTHS['very_long']), nullable=True)  # Auto-generated summary
    
    # Topic relationship
    topic_key = Column(String(STRING_LENGTHS['medium']), ForeignKey('topics.topic_key', ondelete='CASCADE'), nullable=False)
    primary_topic_key = Column(String(STRING_LENGTHS['medium']), ForeignKey('topics.topic_key'), nullable=True)
    
    # Lifecycle
    state = Column(String(50), nullable=True, default='emerging')  # emerging, active, escalated, stabilizing, resolved, archived
    status = Column(String(50), nullable=True)
    
    # Temporal
    start_time = Column(DateTime(timezone=True), nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Volume & Velocity
    mention_count = Column(Integer, default=0)
    volume_current_window = Column(Integer, default=0)
    volume_previous_window = Column(Integer, default=0)
    velocity_percent = Column(Float, default=0.0)
    velocity_score = Column(Float, default=0.0)
    
    # Sentiment (aggregated)
    sentiment_distribution = Column(JSONB, nullable=True)  # {positive: 0.3, negative: 0.6, neutral: 0.1}
    weighted_sentiment_score = Column(Float, nullable=True)
    sentiment_index = Column(Float, nullable=True)  # 0-100
    emotion_distribution = Column(JSONB, nullable=True)  # {anger: 0.4, fear: 0.3, ...}
    emotion_adjusted_severity = Column(Float, nullable=True)
    
    # Priority
    priority_score = Column(Float, default=0.0)  # 0-100
    priority_band = Column(String(20), nullable=True)  # critical, high, medium, low
    
    # Metadata
    top_keywords = Column(ARRAY(Text), nullable=True)
    top_sources = Column(ARRAY(Text), nullable=True)
    regions_impacted = Column(ARRAY(Text), nullable=True)
    entities_mentioned = Column(JSONB, nullable=True)
    
    # Clustering metadata
    cluster_centroid_embedding = Column(JSONB, nullable=True)  # Representative embedding
    similarity_threshold = Column(Float, default=0.75)
    
    # Configuration
    time_window_type = Column(String(20), nullable=True)  # breaking, emerging, sustained
    volume_threshold = Column(Integer, default=50)
    velocity_threshold = Column(Float, default=3.0)
    
    # Flags
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # Legacy field
    
    # Legacy fields (for backward compatibility)
    max_issues = Column(Integer, default=20)  # Per topic limit
    
    # Relationships
    topic = relationship("Topic", back_populates="issues", foreign_keys=[topic_key])
    primary_topic = relationship("Topic", foreign_keys=[primary_topic_key], overlaps="primary_issues")
    issue_mentions = relationship("IssueMention", back_populates="issue", cascade="all, delete-orphan")
    topic_links = relationship("TopicIssueLink", back_populates="issue", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('mention_count >= 0', name='check_mention_count_positive'),
        # Note: issue_slug is now unique globally (not per topic_key)
        Index('idx_topic_issues_topic', 'primary_topic_key'),
        Index('idx_topic_issues_state', 'state'),
        Index('idx_topic_issues_priority', 'priority_score'),
        Index('idx_topic_issues_active', 'is_active', 'state'),
        Index('idx_topic_issues_time', 'start_time', 'last_activity')
    )

class MentionTopic(Base):
    """Junction table: many-to-many relationship between mentions and topics."""
    __tablename__ = 'mention_topics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mention_id = Column(Integer, ForeignKey('sentiment_data.entry_id', ondelete='CASCADE'), nullable=False)
    topic_key = Column(String(STRING_LENGTHS['medium']), ForeignKey('topics.topic_key'), nullable=False)
    
    # Classification scores
    topic_confidence = Column(Float, nullable=False)
    keyword_score = Column(Float)
    embedding_score = Column(Float)
    
    # Issue classification (per topic)
    issue_slug = Column(String(STRING_LENGTHS['long']))
    issue_label = Column(String(STRING_LENGTHS['very_long']))
    issue_confidence = Column(Float)
    issue_keywords = Column(JSONB)  # PostgreSQL JSONB, fallback to JSON if needed
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    mention = relationship("SentimentData")
    topic = relationship("Topic", back_populates="mention_classifications")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('mention_id', 'topic_key', name='uq_mention_topic'),
        CheckConstraint('topic_confidence >= 0.0 AND topic_confidence <= 1.0', name='check_confidence_range')
    )

class OwnerConfig(Base):
    """Owner (president/minister) configurations for topic filtering."""
    __tablename__ = 'owner_configs'
    
    owner_key = Column(String(STRING_LENGTHS['medium']), primary_key=True)
    owner_name = Column(String(STRING_LENGTHS['long']), nullable=False)
    owner_type = Column(String(STRING_LENGTHS['short']))  # 'president', 'minister', etc.
    topics: list[str] = Column(ARRAY(Text))  # Array of topic_keys this owner cares about
    priority_topics: list[str] = Column(ARRAY(Text))  # High-priority topics
    is_active = Column(Boolean, default=True)
    config_data = Column(JSONB)  # Additional config data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConfigurationSchema(Base):
    """Schema definitions for configuration categories."""
    __tablename__ = 'configuration_schemas'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(STRING_LENGTHS['medium']), unique=True, nullable=False, index=True)
    schema_definition = Column(JSONB, nullable=False)  # JSON schema for validation
    default_values = Column(JSONB, nullable=False)  # Default config values
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemConfiguration(Base):
    """System configuration values stored in database."""
    __tablename__ = 'system_configurations'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(STRING_LENGTHS['medium']), nullable=False, index=True)
    config_key = Column(String(STRING_LENGTHS['config_key']), nullable=False)  # Key without category prefix
    config_value = Column(JSONB, nullable=False)  # Stores any type (int, string, bool, object, array)
    config_type = Column(String(50), nullable=False)  # 'int', 'float', 'bool', 'string', 'json', 'array'
    description = Column(Text)
    default_value = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    __table_args__ = (
        UniqueConstraint('category', 'config_key', name='uq_category_config_key'),
        Index('idx_category_key', 'category', 'config_key'),
    )


class ConfigurationAuditLog(Base):
    """Audit log for configuration changes."""
    __tablename__ = 'configuration_audit_log'
    
    id = Column(Integer, primary_key=True)
    category = Column(String(STRING_LENGTHS['medium']), nullable=False, index=True)
    config_key = Column(String(STRING_LENGTHS['config_key']), nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    change_reason = Column(Text)
    
    __table_args__ = (
        Index('idx_changed_at', 'changed_at'),
    )


# ============================================
# Issue System Models (Week 1 - Schema Revamp)
# ============================================

class IssueMention(Base):
    """Junction table: issue ↔ mentions (clustering-based)."""
    __tablename__ = 'issue_mentions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id = Column(UUID(as_uuid=True), ForeignKey('topic_issues.id', ondelete='CASCADE'), nullable=False)
    mention_id = Column(Integer, ForeignKey('sentiment_data.entry_id', ondelete='CASCADE'), nullable=False)
    
    # Clustering metadata
    similarity_score = Column(Float, nullable=False)  # How similar to issue cluster
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Denormalized
    topic_key = Column(String(STRING_LENGTHS['medium']), nullable=True)
    
    # Relationships
    issue = relationship("TopicIssue", back_populates="issue_mentions")
    mention = relationship("SentimentData")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('issue_id', 'mention_id', name='uq_issue_mention'),
        Index('idx_issue_mentions_issue', 'issue_id'),
        Index('idx_issue_mentions_mention', 'mention_id'),
        Index('idx_issue_mentions_topic', 'topic_key')
    )


class TopicIssueLink(Base):
    """Many-to-many: topic ↔ issue links."""
    __tablename__ = 'topic_issue_links'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_key = Column(String(STRING_LENGTHS['medium']), ForeignKey('topics.topic_key', ondelete='CASCADE'), nullable=False)
    issue_id = Column(UUID(as_uuid=True), ForeignKey('topic_issues.id', ondelete='CASCADE'), nullable=False)
    
    # Per-topic statistics
    mention_count = Column(Integer, default=0)
    max_issues = Column(Integer, default=20)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    topic = relationship("Topic")
    issue = relationship("TopicIssue", back_populates="topic_links")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('topic_key', 'issue_id', name='uq_topic_issue_link'),
        Index('idx_topic_issue_links_topic', 'topic_key'),
        Index('idx_topic_issue_links_issue', 'issue_id')
    )


# ============================================
# Sentiment System Models (Week 1 - Schema Revamp)
# ============================================

class SentimentAggregation(Base):
    """Aggregated sentiment by topic/issue/entity."""
    __tablename__ = 'sentiment_aggregations'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregation_type = Column(String(50), nullable=False)  # 'topic', 'issue', 'entity'
    aggregation_key = Column(String(200), nullable=False)  # topic_key, issue_id, entity_name
    time_window = Column(String(20), nullable=False)  # '15m', '1h', '24h', '7d', '30d'
    
    # Aggregated metrics
    weighted_sentiment_score = Column(Float, nullable=True)
    sentiment_index = Column(Float, nullable=True)  # 0-100
    sentiment_distribution = Column(JSONB, nullable=True)  # {positive: 0.3, negative: 0.6, neutral: 0.1}
    emotion_distribution = Column(JSONB, nullable=True)  # {anger: 0.4, fear: 0.3, ...}
    emotion_adjusted_severity = Column(Float, nullable=True)
    
    # Metadata
    mention_count = Column(Integer, nullable=True)
    total_influence_weight = Column(Float, nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('aggregation_type', 'aggregation_key', 'time_window', name='uq_sentiment_aggregation'),
        Index('idx_sentiment_agg_type_key', 'aggregation_type', 'aggregation_key'),
        Index('idx_sentiment_agg_time', 'calculated_at')
    )


class SentimentTrend(Base):
    """Sentiment trends over time."""
    __tablename__ = 'sentiment_trends'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregation_type = Column(String(50), nullable=False)
    aggregation_key = Column(String(200), nullable=False)
    time_window = Column(String(20), nullable=False)
    
    # Trend data
    current_sentiment_index = Column(Float, nullable=True)
    previous_sentiment_index = Column(Float, nullable=True)
    trend_direction = Column(String(20), nullable=True)  # 'improving', 'deteriorating', 'stable'
    trend_magnitude = Column(Float, nullable=True)
    
    # Periods
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    previous_period_start = Column(DateTime(timezone=True), nullable=True)
    previous_period_end = Column(DateTime(timezone=True), nullable=True)
    
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Constraints
    __table_args__ = (
        Index('idx_sentiment_trends_type_key', 'aggregation_type', 'aggregation_key'),
        Index('idx_sentiment_trends_time', 'calculated_at')
    )


class TopicSentimentBaseline(Base):
    """Topic sentiment baselines for normalization."""
    __tablename__ = 'topic_sentiment_baselines'
    
    topic_key = Column(String(STRING_LENGTHS['medium']), ForeignKey('topics.topic_key'), primary_key=True)
    baseline_sentiment_index = Column(Float, nullable=True)  # Historical average (0-100)
    baseline_calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    lookback_days = Column(Integer, default=30)
    sample_size = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    topic = relationship("Topic", back_populates="sentiment_baseline") 
