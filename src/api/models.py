from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, Index, Text, Boolean, ForeignKey, UniqueConstraint, JSON, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base
import datetime

# Import Base from database.py
from .database import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), nullable=True)
    ministry = Column(String(50), nullable=True)
    name = Column(String(200), nullable=True)
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
    alert_id = Column(Integer, nullable=True)
    published_at = Column(DateTime(timezone=False), nullable=True) # Specific 'published_at' column
    source_type = Column(String, nullable=True)
    country = Column(String, nullable=True)
    favorite = Column(Boolean, nullable=True)
    tone = Column(String, nullable=True)
    source_name = Column(String, nullable=True)
    parent_url = Column(String, nullable=True)
    parent_id = Column(String, nullable=True) # Assuming string ID
    children = Column(Integer, nullable=True)
    direct_reach = Column(Integer, nullable=True)
    cumulative_reach = Column(Integer, nullable=True)
    domain_reach = Column(Integer, nullable=True)
    tags = Column(String, nullable=True) # Storing tags as a string, consider JSON if needed
    score = Column(Float, nullable=True) # General score field
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
    sentiment_label = Column(String, nullable=True) # Keep existing sentiment fields
    sentiment_score = Column(Float, nullable=True)
    sentiment_justification = Column(Text, nullable=True) # Field for ChatGPT justification
    
    # Enhanced location classification fields
    location_label = Column(String, nullable=True)
    location_confidence = Column(Float, nullable=True)
    
    # Issue mapping fields
    issue_label = Column(String, nullable=True)
    issue_slug = Column(String, nullable=True)
    issue_confidence = Column(Float, nullable=True)
    issue_keywords = Column(JSON, nullable=True)
    ministry_hint = Column(String(50), nullable=True)

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
    embedding_model = Column(String(50), nullable=True, default='text-embedding-3-small')
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    
    # Relationship with SentimentData
    sentiment_data = relationship("SentimentData", back_populates="embedding") 