# Standard library imports
import os
import sys
import json
import asyncio
import logging
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

# Third-party imports
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Response, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from dotenv import load_dotenv
import pandas as pd

# Local imports - config
from src.config.path_manager import PathManager
from src.config.config_manager import ConfigManager
from src.config.logging_config import get_logger

# Local imports - exceptions
from src.exceptions import APIError, DatabaseError

# Local imports - utils
from src.utils.common import parse_datetime

# Local imports - agent
from src.agent.core import SentimentAnalysisAgent

# Local imports - API modules
from . import models, database, admin
from .database import SessionLocal, engine, get_db
from .middlewares import UsageTrackingMiddleware
from .presidential_service import add_presidential_endpoints
from .auth import get_current_user_id

# Module-level configuration
load_dotenv()

# --- Create tables on startup (or use Alembic) ---
# database.Base.metadata.create_all(bind=engine) # Use Alembic upgrade instead
# ----------------------------------------------------

# Use centralized logging configuration
try:
    from src.config.logging_config import get_logger
    logger = get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# Initialize PathManager for centralized path management
_path_manager = PathManager()

app = FastAPI()

# Load CORS origins from ConfigManager
try:
    from config.config_manager import ConfigManager
    config = ConfigManager()
    origins = config.get_list("api.cors_origins", [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://13.202.48.110:3000",
        "http://13.202.48.110:3001",
        "https://*.railway.app",
        "https://*.up.railway.app"
    ])
except Exception as e:
    logger.warning(f"Could not load ConfigManager for CORS origins, using defaults: {e}")
    origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://13.202.48.110:3000",
        "http://13.202.48.110:3001",
        "https://*.railway.app",
        "https://*.up.railway.app"
    ]

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Loaded from ConfigManager (editable via database)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add the usage tracking middleware
app.add_middleware(UsageTrackingMiddleware)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Security: Debug endpoints removed - these were a security risk
# FastAPI will automatically return 404 for undefined routes, which is safer


# Include the admin router
app.include_router(admin.router)

# Add presidential analysis endpoints
add_presidential_endpoints(app)

# Initialize agent
try:
    agent = SentimentAnalysisAgent(db_factory=SessionLocal)
except Exception as e:
    logger.error(f"Failed to initialize SentimentAnalysisAgent: {e}", exc_info=True)
    # Decide how to handle this error - exit, run without agent?
    agent = None # Or a dummy agent

# WebSocket endpoint removed - not needed

# Email services removed - mail_sender and report_scheduler not used

# === In-memory data storage ===
# Use pandas DataFrames to store the data
# latest_data_df: Optional[pd.DataFrame] = None
# previous_data_df: Optional[pd.DataFrame] = None
# last_update_time: Optional[datetime] = None
# =============================

# UserSignup model removed - /user/register endpoint removed


class DataRecord(BaseModel):
    """
    Pydantic model for data records matching SentimentData model fields.
    
    This model represents a single data record with all possible fields from various
    data sources (RSS feeds, social media, news articles, etc.). All fields are optional
    to accommodate different data source formats.
    
    Attributes:
        title: Article or post title
        description: Article description or summary
        content: Full content text
        url: Source URL
        published_date: Publication date
        source: Source name
        source_url: Source website URL
        query: Search query used to find this record
        language: Content language
        platform: Platform name (e.g., "twitter", "facebook", "rss")
        date: Specific date field
        text: Text content
        file_source: Source file name
        id: Original ID from source
        alert_id: Alert identifier
        published_at: Specific published timestamp
        source_type: Type of source
        country: Country code
        favorite: Whether marked as favorite
        tone: Sentiment tone
        source_name: Name of the source
        parent_url: Parent URL (for threaded content)
        parent_id: Parent ID (for threaded content)
        children: Number of child items
        direct_reach: Direct reach metric
        cumulative_reach: Cumulative reach metric
        domain_reach: Domain reach metric
        tags: Tags or categories
        score: General relevance score
        alert_name: Alert name
        type: Content type
        post_id: Post identifier
        retweets: Number of retweets
        likes: Number of likes
        user_location: User location
        comments: Number of comments
        user_name: User display name
        user_handle: User handle/username
        user_avatar: User avatar URL
        sentiment_label: Sentiment classification label
        sentiment_score: Sentiment score (-1.0 to 1.0)
        sentiment_justification: Explanation of sentiment analysis
    """
    # Updated to match SentimentData model fields derived from CSV header
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[datetime] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    query: Optional[str] = None
    language: Optional[str] = None
    platform: Optional[str] = None
    date: Optional[datetime] = None # Specific 'date' field
    text: Optional[str] = None
    file_source: Optional[str] = None
    id: Optional[str] = None # This corresponds to 'original_id' in the DB model
    published_at: Optional[datetime] = None # Specific 'published_at' field
    source_type: Optional[str] = None
    country: Optional[str] = None
    favorite: Optional[bool] = None
    tone: Optional[str] = None
    source_name: Optional[str] = None
    parent_url: Optional[str] = None
    parent_id: Optional[str] = None
    direct_reach: Optional[int] = None
    cumulative_reach: Optional[int] = None
    domain_reach: Optional[int] = None
    tags: Optional[str] = None # Consider Union[List[str], str] or just str
    alert_name: Optional[str] = None
    type: Optional[str] = None # 'type' field
    post_id: Optional[str] = None
    retweets: Optional[int] = None
    likes: Optional[int] = None
    user_location: Optional[str] = None
    comments: Optional[int] = None
    user_name: Optional[str] = None
    user_handle: Optional[str] = None
    user_avatar: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_justification: Optional[str] = None

# DataUpdateRequest removed - /data/update endpoint removed

# CommandRequest removed - /command endpoint removed

# WebSocket endpoint and broadcast_update removed - not needed

# /status endpoint removed - not needed

# /command endpoint removed - not needed

# Legacy /data/update endpoint removed - replaced by pipeline-based data collection

# /latest-data endpoint removed - not needed

# /config endpoints (GET/POST) removed - not needed

# /target endpoints (GET/POST) removed - not needed
# Note: TargetIndividualConfig model may still be used elsewhere, check before removing

# /target-configs endpoints (GET/POST) removed - not needed

# Duplicate endpoint /agent/trigger-run-parallel removed - use /agent/test-cycle-no-auth instead

# /agent/automatic-scheduling/* endpoints removed - not used (we use run_cycles.sh instead)

# Duplicate endpoint /agent/test-cycle removed - use /agent/test-cycle-no-auth instead

@app.post("/agent/test-cycle-no-auth", status_code=status.HTTP_202_ACCEPTED)
async def test_single_cycle_no_auth(
    background_tasks: BackgroundTasks, 
    test_user_id: Optional[str] = None,
    use_existing_data: bool = Query(False, description="If True, skips data collection/loading/deduplication and uses existing embeddings/sentiment from database"),
    skip_collection_only: bool = Query(False, description="If True, skips collection/loading/deduplication but processes ALL existing records normally (with OpenAI calls)")
) -> Dict[str, Any]:
    """
    Test endpoint to run a single automatic cycle without authentication (for testing purposes only).
    
    Args:
        test_user_id: User ID to process (optional, will use first available user if not provided)
        use_existing_data: If True, skips collection/loading/deduplication and uses existing embeddings/sentiment
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
    
    try:
        # Get a user_id from database if not provided
        if not test_user_id:
            with SessionLocal() as db:
                # Try to get first user with target config
                target_config = db.query(models.TargetIndividualConfiguration).first()
                if target_config and target_config.user_id:
                    test_user_id = str(target_config.user_id)
                else:
                    # Try to get any user
                    user = db.query(models.User).first()
                    if user:
                        test_user_id = str(user.id)
                    else:
                        raise HTTPException(status_code=400, detail="No users found in database. Please create a user first.")
        
        logger.info(f"Test cycle (no-auth) triggered for user: {test_user_id} (use_existing_data={use_existing_data}, skip_collection_only={skip_collection_only})")
        
        # Run a single cycle in background
        if agent.parallel_enabled:
            background_tasks.add_task(agent.run_single_cycle_parallel, user_id=test_user_id, use_existing_data=use_existing_data, skip_collection_only=skip_collection_only)
        else:
            background_tasks.add_task(agent._run_automatic_collection, user_id=test_user_id)
        
        # Get worker configuration for response
        worker_config = {
            "collector_workers": agent.max_collector_workers,
            "sentiment_workers": agent.max_sentiment_workers,
            "location_workers": agent.max_location_workers,
            "sentiment_batch_size": agent.sentiment_batch_size,
            "location_batch_size": agent.location_batch_size,
            "parallel_enabled": agent.parallel_enabled
        }
        
        # Use PathManager for log file path
        log_file_path = str(_path_manager.logs_scheduling)
        
        if skip_collection_only:
            mode_note = "Skip collection mode: Skipping Collection/Loading/Deduplication, processing ALL existing records normally (with OpenAI calls)"
        elif use_existing_data:
            mode_note = "Using existing data mode: Skipping Collection/Loading/Deduplication, using existing embeddings/sentiment"
        else:
            mode_note = "Full cycle: Collection -> Data Loading -> Deduplication -> Sentiment Analysis -> Location Classification"
        
        return {
            "status": "success",
            "message": f"Test cycle started for user {test_user_id}. Check {log_file_path} for detailed progress.",
            "user_id": test_user_id,
            "use_existing_data": use_existing_data,
            "skip_collection_only": skip_collection_only,
            "worker_configuration": worker_config,
            "log_file": log_file_path,
            "note": f"This is a one-time test cycle. It will run in the background. {mode_note}"
        }
        
    except Exception as e:
        api_error = APIError(
            f"Error starting test cycle: {str(e)}",
            details={"test_user_id": test_user_id, "error_type": type(e).__name__}
        )
        logger.error(str(api_error), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting test cycle: {str(e)}")

# SupabaseSignupPayload models removed - /user/register endpoint removed

# /user/register endpoint removed - not needed


# /admin/sync-users endpoint removed - not needed

@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.
    
    Performs initialization tasks when the API service starts:
    - Logs database connection pool configuration
    - Creates database tables if database doesn't exist
    - Creates initial admin user if none exists
    - Logs enabled collectors from target configuration
    - Ensures agent background tasks are not auto-started
    
    This function is called automatically by FastAPI when the application starts.
    """
    logger.info("=" * 60)
    logger.info("API Service Starting Up")
    logger.info("=" * 60)
    
    # Log database connection pool info (from database.py configuration)
    logger.info(f"Database Connection Pool:")
    logger.info(f"  - Pool Size: 30")
    logger.info(f"  - Max Overflow: 20")
    logger.info(f"  - Total Max Connections: 50")
    
    # Ensure database tables are created (only if database doesn't exist)
    try:
        import os
        db_file_path = "sentiment_analysis_local.db"
        if not os.path.exists(db_file_path):
            logger.info("Creating database tables...")
            from .database import create_tables
            success = create_tables()
            if success:
                logger.info("Database tables created successfully")
            else:
                logger.error("Failed to create database tables")
        else:
            logger.debug(f"Database file exists at {db_file_path}, using existing data")
    except Exception as e:
        logger.error(f"Error handling database: {e}", exc_info=True)
    
    # Report scheduler initialization removed - not used
    
    # Set up initial admin user if none exists
    try:
        db = SessionLocal()
        admin_user = db.query(models.User).filter(models.User.is_admin == True).first()
        if not admin_user:
            try:
                # Create first admin user
                admin_id = uuid.uuid4()
                admin_email = "admin@example.com"  # You should change this in production
                admin_user = models.User(
                    id=admin_id,
                    email=admin_email,
                    is_admin=True
                )
                logger.info("Creating initial admin user")
                db.add(admin_user)
                db.commit()
                logger.info(f"Created initial admin user with ID: {admin_id}")
            except Exception as e:
                logger.error(f"Failed to create admin user: {e}")
                db.rollback()
        db.close()
    except Exception as e:
        logger.error(f"Error checking/creating admin user: {e}")

    # Optional: Start the agent if it has a background loop
    if agent and hasattr(agent, 'start'):
        try:
             logger.debug("Ensuring SentimentAnalysisAgent background tasks are NOT started automatically.")
             # agent.start() # <<< MAKE SURE THIS LINE IS COMMENTED OUT
             logger.debug("SentimentAnalysisAgent start() call is correctly commented out in startup_event.")
        except Exception as e:
             # This block should ideally not be reached if agent.start() is commented out
             logger.error(f"Unexpected error related to agent start in startup_event: {e}", exc_info=True)

    # Log enabled collectors from target configuration
    try:
        from src.collectors.target_config_manager import TargetConfigManager
        config_manager = TargetConfigManager()
        
        if config_manager.targets:
            logger.info("Enabled Collectors (from target config):")
            for target_id, target_config in config_manager.targets.items():
                enabled_sources = []
                for source_type, source_config in target_config.sources.items():
                    if source_config.enabled:
                        enabled_sources.append(source_type)
                
                if enabled_sources:
                    logger.info(f"  - {target_config.name} ({target_id}): {', '.join(sorted(enabled_sources))}")
                else:
                    logger.info(f"  - {target_config.name} ({target_id}): No collectors enabled")
        else:
            logger.info("No target configurations found")
    except Exception as e:
        logger.debug(f"Could not load enabled collectors from target config: {e}")
    
    logger.info("=" * 60)
    logger.info("API Service startup complete - Ready to accept requests")
    logger.info("=" * 60)

def apply_target_filtering_to_media_data(db: Session, all_data: List, user_id: Optional[str], endpoint_name: str) -> List:
    """Helper function to apply target individual filtering to media data"""
    if not user_id:
        return all_data
    
    try:
        from uuid import UUID
        user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
        target_config = db.query(models.TargetIndividualConfiguration)\
                         .filter(models.TargetIndividualConfiguration.user_id == user_uuid)\
                         .order_by(models.TargetIndividualConfiguration.created_at.desc())\
                         .first()
        
        if target_config:
            from .data_cache import sentiment_cache
            logger.info(f"Applying target filtering for {endpoint_name}: {target_config.individual_name}")
            filtered_data = sentiment_cache.filter_by_target_config(all_data, target_config)
            logger.info(f"Filtered {len(all_data)} to {len(filtered_data)} records for target individual")
            return filtered_data
        else:
            logger.info(f"No target config found for user {user_id} in {endpoint_name}")
    except Exception as e:
        logger.warning(f"Error applying target filtering in {endpoint_name}: {e}")
    
    return all_data

# React app serving code removed - backend should not serve frontend
# Frontend should be served separately (e.g., via nginx, Vercel, etc.)
# Root endpoints for health checks
@app.get("/")
async def root():
    """Root endpoint for health checks"""
    return {
        "status": "ok",
        "message": "Backend API is running",
        "health_check": "/health",
        "api_docs": "/docs",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/")
async def root_post():
    """Handle POST requests to root path (for health checks)"""
    return {
        "status": "ok",
        "message": "Backend API is running",
        "health_check": "/health",
        "timestamp": datetime.now().isoformat()
    }
