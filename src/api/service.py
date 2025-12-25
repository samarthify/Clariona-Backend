from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks, Depends, Response, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import pandas as pd
from pathlib import Path
from pydantic import BaseModel, EmailStr, Field
import logging
import uuid
from uuid import UUID
# Database imports
from sqlalchemy.orm import Session
from sqlalchemy import desc
from . import models, database, admin
from .database import SessionLocal, engine, get_db
from .middlewares import UsageTrackingMiddleware
from sqlalchemy import text
# Import the agent
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.core import SentimentAnalysisAgent
from utils.mail_sender import MailSender
from utils.scheduled_reports import ReportScheduler

# Import presidential analysis service
from .presidential_service import add_presidential_endpoints

# Import the auth dependency
from .auth import get_current_user_id

from dotenv import load_dotenv
load_dotenv()

# --- Create tables on startup (or use Alembic) ---
# database.Base.metadata.create_all(bind=engine) # Use Alembic upgrade instead
# ----------------------------------------------------

logger = logging.getLogger("api_service")

app = FastAPI()

origins=[
	"http://localhost:3000",
	"http://13.202.48.110:3000",
    "http://localhost:3001",  # Add this
    "http://13.202.48.110:3001",
    # Railway domains - will be updated with actual domain
    "https://*.railway.app",
    "https://*.up.railway.app",
]
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # In production, replace with specific origins
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

# Security: Block access to sensitive files and log suspicious requests
SENSITIVE_PATHS = {
    "/.env", "/.env.local", "/.env.production", "/.env.development",
    "/.git", "/.git/config", "/.gitignore", "/.gitattributes",
    "/config.json", "/package.json", "/composer.json",
    "/wp-config.php", "/wp-admin", "/phpinfo.php",
    "/.htaccess", "/.htpasswd", "/web.config",
    "/admin", "/administrator", "/phpmyadmin",
}

@app.get("/.env")
@app.get("/.env.local")
@app.get("/.env.production")
@app.get("/.git")
@app.get("/.git/config")
@app.post("/.env")
@app.post("/.env.local")
async def block_sensitive_files(request: Request):
    """Block access to sensitive files and log security events"""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get('user-agent', 'unknown')
    logger.warning(f"Security: Blocked access attempt to {request.url.path} from {client_ip} (User-Agent: {user_agent})")
    raise HTTPException(status_code=404, detail="Not found")


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

# Store active WebSocket connections
active_connections: List[WebSocket] = []

# Initialize email services
mail_sender = MailSender()
report_scheduler = None

# === In-memory data storage ===
# Use pandas DataFrames to store the data
# latest_data_df: Optional[pd.DataFrame] = None
# previous_data_df: Optional[pd.DataFrame] = None
# last_update_time: Optional[datetime] = None
# =============================

class UserSignup(BaseModel):
    id: str
    email: EmailStr
    name: str
    password: str
    is_admin: Optional[bool] = False  # Optional, defaults to False


class DataRecord(BaseModel):
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
    alert_id: Optional[int] = None
    published_at: Optional[datetime] = None # Specific 'published_at' field
    source_type: Optional[str] = None
    country: Optional[str] = None
    favorite: Optional[bool] = None
    tone: Optional[str] = None
    source_name: Optional[str] = None
    parent_url: Optional[str] = None
    parent_id: Optional[str] = None
    children: Optional[int] = None
    direct_reach: Optional[int] = None
    cumulative_reach: Optional[int] = None
    domain_reach: Optional[int] = None
    tags: Optional[str] = None # Consider Union[List[str], str] or just str
    score: Optional[float] = None # General score
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

class DataUpdateRequest(BaseModel):
    user_id: str # Added user_id field
    data: List[DataRecord]

class CommandRequest(BaseModel):
    command: str
    params: Optional[Dict[str, Any]] = None

async def broadcast_update(message: Dict[str, Any]):
    """Broadcast updates to all connected clients"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            # Remove connection safely if send fails
            if connection in active_connections:
                active_connections.remove(connection)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "status":
                # Avoid blocking websocket: run agent call in executor or make agent async
                status_data = agent.get_status() # Assuming get_status is fast
                await websocket.send_json(status_data)
    except Exception as e:
        logger.warning(f"WebSocket error or connection closed: {e}")
    finally:
        if websocket in active_connections:
             active_connections.remove(websocket)

@app.get("/status")
async def get_status():
    """Get current agent status"""
    # This likely doesn't need DB access unless status includes DB stats
    return agent.get_status()

@app.post("/command")
async def execute_command(request: CommandRequest):
    """Execute a command on the agent"""
    # This likely doesn't need DB access unless command involves DB
    result = agent.execute_command(request.command, request.params)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    # Avoid blocking: run get_status in executor if it becomes slow
    status_data = agent.get_status()
    await broadcast_update({'type': 'status_update', 'data': status_data})
    return result

def parse_datetime(dt_input: Optional[Any]) -> Optional[datetime]:
    """Helper function to parse and clean datetime fields"""
    if dt_input is None:
        return None
    
    parsed_dt = None
    if isinstance(dt_input, str):
        # Strip whitespace
        date_str = dt_input.strip()
        
        # Skip invalid or empty dates
        if date_str.lower() in ['none', 'nan', '', 'unknown']:
            return None
        
        try:
            # Handle Twitter date format (e.g., Fri Nov 24 17:49:36 +0000 2023)
            import re
            twitter_pattern = r'[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[+]\d{4}\s+\d{4}'
            if re.match(twitter_pattern, date_str):
                parsed_dt = datetime.strptime(date_str, '%a %b %d %H:%M:%S +0000 %Y')
            # Handle ISO format with timezone (e.g., 2025-03-21T12:19:52.000Z)
            elif 'T' in date_str and ('Z' in date_str or '+' in date_str):
                parsed_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            # Handle standard datetime format (e.g., 2025-03-14 16:17:49)
            elif re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', date_str):
                parsed_dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            # Try ISO format as fallback
            else:
                parsed_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse timestamp: {dt_input}. Error: {e}. Setting to None.")
            return None
    elif isinstance(dt_input, datetime):
        parsed_dt = dt_input
    else:
        logger.warning(f"Unexpected type for timestamp: {type(dt_input)}. Setting to None.")
        return None

    # Ensure the datetime is naive (no timezone)
    if parsed_dt and parsed_dt.tzinfo:
        return parsed_dt.replace(tzinfo=None)
    
    return parsed_dt

@app.post("/data/update")
async def update_data(request: DataUpdateRequest, db: Session = Depends(get_db)):
    try:
        user_id = request.user_id  # Get user_id from request
        new_records = request.data
        if not new_records:
            return {"status": "success", "message": "No new data received."}

        current_run_time = datetime.now()  # Timestamp for this batch
        db_objects = []  # To store all the records to be added

        for record in new_records:
            logger.debug(f"Row: {record}")
            db_obj = models.SentimentData(
                user_id=user_id, # Assign the user ID from the request
                run_timestamp=current_run_time,
                 # Map all fields from DataRecord to SentimentData
                title=record.title,
                description=record.description,
                content=record.content,
                url=record.url,
                published_date=parse_datetime(record.published_date),
                source=record.source,
                source_url=record.source_url,
                query=record.query,
                language=record.language,
                platform=record.platform,
                date=parse_datetime(record.date), # Specific 'date' field
                text=record.text,
                file_source=record.file_source,
                original_id=record.id, # Map request 'id' to DB 'original_id'
                alert_id=record.alert_id,
                published_at=parse_datetime(record.published_at), # Specific 'published_at'
                source_type=record.source_type,
                country=record.country,
                favorite=record.favorite,
                tone=record.tone,
                source_name=record.source_name,
                parent_url=record.parent_url,
                parent_id=record.parent_id,
                children=record.children,
                direct_reach=record.direct_reach,
                cumulative_reach=record.cumulative_reach,
                domain_reach=record.domain_reach,
                tags=record.tags, # Assuming tags is a string; adjust if it's list/JSON
                score=record.score,
                alert_name=record.alert_name,
                type=record.type,
                post_id=record.post_id,
                retweets=record.retweets,
                likes=record.likes,
                user_location=record.user_location,
                comments=record.comments,
                user_name=record.user_name,
                user_handle=record.user_handle,
                user_avatar=record.user_avatar,
                sentiment_label=record.sentiment_label,
                sentiment_score=record.sentiment_score,
                sentiment_justification=record.sentiment_justification # Added justification
            )
            db_objects.append(db_obj)

        if db_objects:
            db.add_all(db_objects)
            db.commit()  # Commit the transaction
            logger.info(f"Successfully added {len(db_objects)} records to the database.")
            
            # Invalidate cache when new data is added
            try:
                from .data_cache import sentiment_cache
                sentiment_cache.clear_cache()
                logger.info("Cache invalidated due to new data")
            except Exception as cache_error:
                logger.warning(f"Failed to invalidate cache: {cache_error}")
            
            return {"status": "success", "message": f"Data updated with {len(db_objects)} records."}
        else:
            return {"status": "success", "message": "No records to add."}

    except Exception as e:
        db.rollback()  # Rollback in case of error during commit
        logger.error(f"Error updating database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating database: {e}")

@app.get("/latest-data")
async def get_latest_data(db: Session = Depends(get_db), user_id: Optional[str] = None):
    """Get processed data with AI justification (any content) with optional target individual filtering."""
    try:
        logger.info(f"Latest data endpoint called with user_id: {user_id}")
        from .data_cache import sentiment_cache
        
        # Test database connection first
        try:
            db.execute(text("SELECT 1"))
            logger.info("Database connection successful")
        except Exception as db_error:
            logger.error(f"Database connection failed: {str(db_error)}")
            return {"status": "error", "message": f"Database connection failed: {str(db_error)}"}
        
        # Get AI processed data from cache
        logger.info("Loading AI processed data from cache...")
        results = sentiment_cache.get_ai_processed_data(db)
        
        if not results:
            return {"status": "error", "message": "No data with AI justification available."}
        
        # Target individual filtering
        target_config = None
        if user_id:
            try:
                # Convert string user_id to UUID for database query
                from uuid import UUID
                user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
                
                # Get target individual configuration for the user
                target_config = db.query(models.TargetIndividualConfiguration)\
                                 .filter(models.TargetIndividualConfiguration.user_id == user_uuid)\
                                 .order_by(models.TargetIndividualConfiguration.created_at.desc())\
                                 .first()
                
                if target_config:
                    logger.info(f"Found target config for user {user_id}: {target_config.individual_name} with {len(target_config.query_variations)} variations")
                    
                    # Apply target filtering using cache
                    results = sentiment_cache.filter_by_target_config(results, target_config)
                    logger.info(f"Applied target individual filtering for user {user_id}")
                else:
                    logger.info(f"No target config found for user {user_id}, returning general data")
            except Exception as config_error:
                logger.warning(f"Error getting target config for user {user_id}: {str(config_error)}, returning general data")
        
        if target_config:
            logger.info(f"Found {len(results)} records with AI justification (FILTERED for {target_config.individual_name})")
        else:
            logger.info(f"Found {len(results)} records with AI justification (NO TARGET FILTERING)")
        
        # Apply deduplication using cache
        deduplicated_results = sentiment_cache.deduplicate_data(results)
        logger.info(f"After deduplication: {len(deduplicated_results)} unique records")
        
        data_list = [row.to_dict() for row in deduplicated_results]

        return {
            "status": "success",
            "data": data_list,
            "record_count": len(data_list),
            "user_id": user_id,
            "target_individual": target_config.individual_name if target_config else "No target configured",
            "note": f"Data with AI justification - Target filtering {'ENABLED' if target_config else 'DISABLED'}, Deduplication ENABLED, Cache ENABLED"
        }
    except Exception as e:
        logger.error(f"Error fetching data from cache: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"Error fetching data: {str(e)}"}

@app.get("/config")
async def get_config():
    """Get current agent configuration"""
    return {"status": "success", "data": agent.config}

@app.post("/config")
async def update_config(config: Dict[str, Any]):
    """Update agent configuration"""
    result = agent.execute_command('update_config', config)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])
    return result

# Update model for target individual management
class TargetIndividualConfig(BaseModel):
    individual_name: str
    query_variations: List[str]

@app.get("/target")
async def get_target_individual(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    """Get the target individual configuration for the authenticated user."""
    # --- Added detailed logging --- 
    try:
        # Filter by user_id
        logger.debug(f"get_target_individual: Querying DB for TargetIndividualConfiguration with user_id = {user_id}")
        config = db.query(models.TargetIndividualConfiguration)\
                 .filter(models.TargetIndividualConfiguration.user_id == user_id)\
                 .order_by(models.TargetIndividualConfiguration.created_at.desc())\
                 .first()
        
        logger.debug(f"get_target_individual: DB query result: {config}") # Log query result
        # --- End added logging ---

        if not config:
            # Return default values if no configuration is found
            default_data = TargetIndividualConfig(individual_name="Default", query_variations=[]).dict()
            return JSONResponse(content={"status": "success", "data": default_data})
            
        # Convert DB model to Pydantic model
        config_data = TargetIndividualConfig(
            individual_name=config.individual_name,
            query_variations=config.query_variations # Assumes query_variations is stored as JSON
        )
        
        # Return explicit success structure
        return JSONResponse(content={"status": "success", "data": config_data.dict()})
    except Exception as e:
        logger.error(f"Error getting target config: {e}", exc_info=True)
        # Keep raising HTTPException on error
        raise HTTPException(status_code=500, detail=f"Failed to retrieve target individual configuration: {str(e)}")

from uuid import UUID
from .models import User

@app.post("/target")
async def update_target_individual(target_config: TargetIndividualConfig, db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    """Update or create the target individual configuration for the authenticated user."""
    logger.debug(f"Updating target config for user: {user_id}")
    try:
        # Check if a config already exists for this user
        # user = db.query(models.User).filter(models.User.id == user_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        existing_config = db.query(models.TargetIndividualConfiguration)\
                            .filter(models.TargetIndividualConfiguration.user_id == user_id)\
                            .first()
       
        if existing_config:
            # Update existing config
            existing_config.individual_name = target_config.individual_name
            existing_config.query_variations = target_config.query_variations
            db.commit()
            db.refresh(existing_config)
            config_id = existing_config.id
        else:
            new_config = models.TargetIndividualConfiguration(\
                user_id=user_id, # Assign the authenticated user's ID
                individual_name=target_config.individual_name,\
                query_variations=target_config.query_variations,
                created_at=datetime.now()  # Manually set timestamp for SQLite compatibility
            )
            db.add(new_config)
            logger.info(f"Attempting to commit new target config for user {user_id}...") # Log before commit
            db.commit()
            logger.info(f"Successfully committed new target config for user {user_id}.") # Log after commit
            db.refresh(new_config)
            config_id = new_config.id
        
        # Broadcast the update via websocket
        await broadcast_update({
            'type': 'target_update',
            'data': target_config.dict() # Send the newly set config
        })
        
        return {
            "status": "success", 
            "message": "Target individual configuration updated successfully",
            "config_id": config_id,
            "data": target_config.dict()
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating target config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update target individual configuration: {str(e)}")

# Target Config File Management Endpoints
@app.get("/target-configs")
async def get_target_configs():
    """Get the target configurations from the config file."""
    try:
        config_path = Path(__file__).parent.parent.parent / "config" / "target_configs.json"
        logger.info(f"Looking for target config file at: {config_path.absolute()}")
        
        if not config_path.exists():
            logger.error(f"Target config file not found at: {config_path.absolute()}")
            raise HTTPException(status_code=404, detail="Target config file not found")
        
        logger.info(f"Found target config file at: {config_path.absolute()}")
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        return {"status": "success", "data": config_data}
    except Exception as e:
        logger.error(f"Error reading target config file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read target config file: {str(e)}")

@app.post("/target-configs")
async def update_target_configs(config_data: dict):
    """Update the target configurations in the config file."""
    try:
        config_path = Path(__file__).parent.parent.parent / "config" / "target_configs.json"
        logger.info(f"Updating target config file at: {config_path.absolute()}")
        
        # Validate the config structure
        if "targets" not in config_data:
            raise HTTPException(status_code=400, detail="Config must contain 'targets' section")
        
        # Backup the existing config
        backup_path = config_path.with_suffix('.json.backup')
        if config_path.exists():
            import shutil
            shutil.copy2(config_path, backup_path)
            logger.info(f"Backed up existing config to {backup_path}")
        
        # Write the new config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        logger.info("Target config file updated successfully")
        return {"status": "success", "message": "Target configurations updated successfully"}
    except Exception as e:
        logger.error(f"Error updating target config file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update target config file: {str(e)}")

@app.post("/agent/trigger-run-parallel", status_code=status.HTTP_202_ACCEPTED)
async def trigger_agent_run_parallel(background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user_id)):
    """Triggers a parallel data collection and analysis run for the authenticated user."""
    logger.info(f"Parallel agent run triggered manually by user: {user_id}")
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
        
    try:
        # Check if parallel processing is enabled
        if not agent.parallel_enabled:
            raise HTTPException(status_code=400, detail="Parallel processing is disabled in configuration.")
        
        # Call the parallel single cycle method
        background_tasks.add_task(agent.run_single_cycle_parallel, user_id=user_id)
        logger.info("Manual parallel agent data collection task added to background via API.")
        return {"status": "success", "message": f"Parallel agent run triggered for user {user_id}."}
        
    except Exception as e:
        # This exception would likely occur during task *scheduling*, not execution
        logger.error(f"Error scheduling parallel agent run via API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error scheduling parallel agent run: {str(e)}")

@app.post("/agent/automatic-scheduling/start")
async def start_automatic_scheduling():
    """Start automatic scheduling for all configured users."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
    
    try:
        result = agent.start_automatic_scheduling()
        if result:
            scheduler_status = agent.get_scheduler_status()
            return {
                "status": "success",
                "message": "Automatic scheduling started successfully",
                "scheduler_status": scheduler_status
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to start automatic scheduling. Check logs for details.")
    except Exception as e:
        logger.error(f"Error starting automatic scheduling: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting automatic scheduling: {str(e)}")

@app.post("/agent/automatic-scheduling/stop")
async def stop_automatic_scheduling(graceful: bool = False):
    """Stop automatic scheduling.

    If graceful is True, stop scheduling new cycles but allow any in-flight cycles to finish.
    If False (default), force-stop scheduler and active collection threads (current behavior).
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
    
    try:
        agent.stop_automatic_scheduling(graceful=graceful)
        return {
            "status": "success",
            "message": "Automatic scheduling stopped successfully",
            "graceful": graceful
        }
    except Exception as e:
        logger.error(f"Error stopping automatic scheduling: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error stopping automatic scheduling: {str(e)}")

@app.get("/agent/automatic-scheduling/status")
async def get_automatic_scheduling_status():
    """Get the current status of automatic scheduling."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
    
    try:
        scheduler_status = agent.get_scheduler_status()
        return {
            "status": "success",
            "scheduler_status": scheduler_status
        }
    except Exception as e:
        logger.error(f"Error getting automatic scheduling status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting automatic scheduling status: {str(e)}")

@app.post("/agent/test-cycle", status_code=status.HTTP_202_ACCEPTED)
async def test_single_cycle(background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user_id)):
    """Test endpoint to run a single automatic cycle once for testing purposes."""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent is not initialized.")
    
    try:
        logger.info(f"Test cycle triggered by user: {user_id}")
        
        # Run a single cycle in background (always use parallel if enabled, otherwise it will use sequential internally)
        if agent.parallel_enabled:
            background_tasks.add_task(agent.run_single_cycle_parallel, user_id=user_id)
        else:
            # If parallel is disabled, use the automatic collection method which handles both modes
            background_tasks.add_task(agent._run_automatic_collection, user_id=user_id)
        
        # Get worker configuration for response
        worker_config = {
            "collector_workers": agent.max_collector_workers,
            "sentiment_workers": agent.max_sentiment_workers,
            "location_workers": agent.max_location_workers,
            "sentiment_batch_size": agent.sentiment_batch_size,
            "location_batch_size": agent.location_batch_size,
            "parallel_enabled": agent.parallel_enabled
        }
        
        return {
            "status": "success",
            "message": f"Test cycle started for user {user_id}. Check logs/automatic_scheduling.log for detailed progress.",
            "user_id": user_id,
            "worker_configuration": worker_config,
            "log_file": "logs/automatic_scheduling.log",
            "note": "This is a one-time test cycle. It will run in the background and complete all phases: Collection -> Data Loading -> Deduplication -> Sentiment Analysis -> Location Classification"
        }
        
    except Exception as e:
        logger.error(f"Error starting test cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting test cycle: {str(e)}")

@app.post("/agent/test-cycle-no-auth", status_code=status.HTTP_202_ACCEPTED)
async def test_single_cycle_no_auth(background_tasks: BackgroundTasks, test_user_id: Optional[str] = None):
    """Test endpoint to run a single automatic cycle without authentication (for testing purposes only)."""
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
        
        logger.info(f"Test cycle (no-auth) triggered for user: {test_user_id}")
        
        # Run a single cycle in background
        if agent.parallel_enabled:
            background_tasks.add_task(agent.run_single_cycle_parallel, user_id=test_user_id)
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
        
        return {
            "status": "success",
            "message": f"Test cycle started for user {test_user_id}. Check logs/automatic_scheduling.log for detailed progress.",
            "user_id": test_user_id,
            "worker_configuration": worker_config,
            "log_file": "logs/automatic_scheduling.log",
            "note": "This is a one-time test cycle. It will run in the background and complete all phases: Collection -> Data Loading -> Deduplication -> Sentiment Analysis -> Location Classification"
        }
        
    except Exception as e:
        logger.error(f"Error starting test cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error starting test cycle: {str(e)}")

class SupabaseSignupPayload(BaseModel):
    id: UUID
    email: EmailStr
          
class SupabaseSignupPayload(BaseModel):
    id: str                     # Supabase user.id (UUID)
    email: EmailStr
    name: str
    password: str               # You may ignore storing this
    is_admin: Optional[bool] = False

@app.post("/user/register")
async def register_user(payload: SupabaseSignupPayload, db: Session = Depends(get_db)):
    print(f"📥 Received register request for: {payload.email}")

    existing_user = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing_user:
        print("⚠️ User already exists")
        return {"status": "success", "message": "User already exists"}

    try:
        # Convert string id to UUID object
        user_uuid = uuid.UUID(payload.id)
        
        new_user = models.User(
            id=user_uuid,
            email=payload.email,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow(),
            is_admin=payload.is_admin,
            api_calls_count=0,
            data_entries_count=0
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        print(f"✅ New user created: {new_user.email}")
        return {"status": "success", "message": "User registered"}
    except Exception as e:
        db.rollback()
        print(f"❌ DB error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/sync-users")
async def sync_users_from_supabase(db: Session = Depends(get_db), _: str = Depends(admin.admin_only)):
    """
    Synchronize users from Supabase auth to local database.
    This would typically call the Supabase admin API.
    """
    try:
        # In a real implementation, you would call the Supabase admin API here
        # For now, we'll just return a placeholder response
        return {"status": "success", "message": "User sync not implemented yet"}
    except Exception as e:
        logger.error(f"Error syncing users: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    global report_scheduler
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
    
    # Initialize scheduler at startup, passing DB factory 
    # Starts without specific recipients - they are configured via API
    try:
        logger.debug("Initializing report scheduler at startup...")
        report_scheduler = ReportScheduler(db_factory=SessionLocal)
        # Optional: Start scheduler immediately? Or wait for config?
        # start_scheduler() # Uncomment if you want it running by default
        logger.debug("Report scheduler initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize report scheduler at startup: {e}", exc_info=True)
        
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

# Mount static files for React frontend
import os
dashboard_build_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "dashboard1", "build")

if os.path.exists(dashboard_build_path):
    app.mount("/static", StaticFiles(directory=os.path.join(dashboard_build_path, "static")), name="static")
    
    # Mount locales directory for i18n
    locales_path = os.path.join(dashboard_build_path, "locales")
    if os.path.exists(locales_path):
        app.mount("/locales", StaticFiles(directory=locales_path), name="locales")
    
    # Serve React app for root route
    @app.get("/")
    async def serve_react_root():
        """Serve React app for root route"""
        index_path = os.path.join(dashboard_build_path, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            return Response(content=content, media_type="text/html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    # Handle POST requests to root (for health checks that use POST)
    @app.post("/")
    async def root_post():
        """Handle POST requests to root path"""
        # Return JSON response for POST health checks
        return {
            "status": "ok",
            "message": "Backend API is running",
            "health_check": "/health",
            "timestamp": datetime.now().isoformat()
        }
    
    # Serve React app for all other non-API routes (React Router)
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve React app for all non-API routes"""
        # If it's an API route, let FastAPI handle it
        if full_path.startswith("api/") or full_path.startswith("health") or full_path.startswith("ws") or full_path.startswith("debug"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Serve index.html for all other routes (React Router)
        index_path = os.path.join(dashboard_build_path, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            return Response(content=content, media_type="text/html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
else:
    # Fallback root handler when frontend build doesn't exist
    # This helps with load balancer health checks
    @app.get("/")
    async def root_fallback():
        """Fallback root endpoint when frontend is not built"""
        return {
            "status": "ok",
            "message": "Backend API is running. Frontend build not found.",
            "health_check": "/health",
            "api_docs": "/docs",
            "timestamp": datetime.now().isoformat()
        }
    
    # Handle POST requests to root (for health checks that use POST)
    @app.post("/")
    async def root_post_fallback():
        """Handle POST requests to root path"""
        return {
            "status": "ok",
            "message": "Backend API is running. Frontend build not found.",
            "health_check": "/health",
            "api_docs": "/docs",
            "timestamp": datetime.now().isoformat()
        }
