import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
import logging
from . import models
from .database import SessionLocal
import uuid
from typing import Optional

logger = logging.getLogger("api_middleware")

class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API usage by users.
    It captures usage metrics and stores them in the database.
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract user_id from request headers or token
        user_id = self._get_user_id_from_request(request)
        
        # Process the request
        response = None
        is_error = False
        error_message = None
        
        try:
            response = await call_next(request)
        except Exception as e:
            is_error = True
            error_message = str(e)
            logger.error(f"Error processing request: {e}")
            # Re-raise the exception to allow FastAPI to handle it
            raise
        finally:
            # Measure execution time
            execution_time = int((time.time() - start_time) * 1000)  # in milliseconds
            
            # Log usage to database if user is authenticated
            if user_id:
                self._log_usage(
                    user_id=user_id,
                    endpoint=request.url.path,
                    execution_time_ms=execution_time,
                    status_code=response.status_code if response else None,
                    is_error=is_error,
                    error_message=error_message
                )
                
                # Update user's API calls count
                self._update_user_metrics(user_id)
                
        return response if response else Response(status_code=500)
    
    def _get_user_id_from_request(self, request: Request) -> Optional[str]:
        """Extract user_id from request authorization header."""
        try:
            from jose import jwt
            import os
            
            # Get JWT token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
                
            # Extract token from header
            token = auth_header.split(" ")[1]
            
            # Get JWT secret from environment
            secret_key = os.getenv("SUPABASE_JWT_SECRET")
            if not secret_key:
                # Try to load from config/.env if not already loaded
                from dotenv import load_dotenv
                from pathlib import Path
                config_env_path = Path(__file__).parent.parent.parent / "config" / ".env"
                if config_env_path.exists():
                    load_dotenv(dotenv_path=config_env_path)
                    secret_key = os.getenv("SUPABASE_JWT_SECRET")
                
            if not secret_key:
                logger.error("SUPABASE_JWT_SECRET not set, cannot decode token")
                return None
            
            # Decode token and extract user_id (sub claim)
            payload = jwt.decode(
                token, 
                secret_key, 
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            
            # Extract user ID from the 'sub' claim
            user_id = payload.get("sub")
            return user_id
        except Exception as e:
            logger.error(f"Error extracting user_id from token: {e}")
            return None
    
    def _log_usage(self, user_id: str, endpoint: str, execution_time_ms: int,
                  status_code: Optional[int], is_error: bool, error_message: Optional[str]):
        """Log API usage to database."""
        try:
            # Create a new database session
            db = SessionLocal()
            
            # Convert string user_id to UUID object
            user_uuid = uuid.UUID(user_id)
            
            # Create a new usage log entry
            usage_log = models.UserSystemUsage(
                user_id=user_uuid,
                endpoint=endpoint,
                execution_time_ms=execution_time_ms,
                status_code=status_code,
                is_error=is_error,
                error_message=error_message
            )
            
            # Add and commit to database
            db.add(usage_log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
        finally:
            db.close()
    
    def _update_user_metrics(self, user_id: str):
        """Update user's API call metrics."""
        try:
            # Create a new database session
            db = SessionLocal()
            
            # Convert string user_id to UUID object
            user_uuid = uuid.UUID(user_id)
            
            # Get the user
            user = db.query(models.User).filter(models.User.id == user_uuid).first()
            
            if user:
                user.api_calls_count += 1
                db.commit()
        except Exception as e:
            logger.error(f"Failed to update user metrics: {e}")
        finally:
            db.close() 