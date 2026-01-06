from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid
from pydantic import BaseModel

from .database import get_db
from . import models
from .auth import get_current_user_id

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Pydantic models for requests/responses
class UserInfo(BaseModel):
    id: str
    email: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_admin: bool
    api_calls_count: int
    data_entries_count: int
    
class UserUsageStats(BaseModel):
    user_id: str
    email: str
    total_api_calls: int
    total_data_entries: int
    recent_calls: int  # calls in last 7 days
    recent_entries: int  # entries in last 7 days
    avg_execution_time: Optional[float] = None  # in milliseconds
    error_rate: float  # percentage of errors

class UsageByDate(BaseModel):
    date: str
    count: int

class DetailedUsageLog(BaseModel):
    id: int
    endpoint: str
    timestamp: datetime
    execution_time_ms: Optional[int]
    status_code: Optional[int]
    is_error: bool
    error_message: Optional[str] = None

# Admin authorization middleware
async def admin_only(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Dependency to ensure only admin users can access these routes"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can access this resource"
        )
    return user_id

# Admin routes
@router.get("/users", response_model=List[UserInfo])
async def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Get list of all users (admin only)"""
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@router.get("/users/{user_id}", response_model=UserInfo)
async def get_user_details(
    user_id: str, 
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Get detailed information about a specific user (admin only)"""
    try:
        uuid_obj = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

@router.get("/usage", response_model=List[UserUsageStats])
async def get_user_usage_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Get usage statistics for all users (admin only)"""
    # Calculate the date range
    now = datetime.utcnow()
    recent_date = now - timedelta(days=days)
    
    results = []
    users = db.query(models.User).all()
    
    for user in users:
        # Get total API calls
        total_api_calls = user.api_calls_count
        
        # Get total data entries
        total_data_entries = db.query(func.count(models.SentimentData.entry_id))\
            .filter(models.SentimentData.user_id == user.id).scalar() or 0
        
        # Get recent API calls (from the usage log)
        recent_calls = db.query(func.count(models.UserSystemUsage.id))\
            .filter(models.UserSystemUsage.user_id == user.id)\
            .filter(models.UserSystemUsage.timestamp >= recent_date).scalar() or 0
        
        # Get recent data entries
        recent_entries = db.query(func.count(models.SentimentData.entry_id))\
            .filter(models.SentimentData.user_id == user.id)\
            .filter(models.SentimentData.created_at >= recent_date).scalar() or 0
        
        # Calculate average execution time
        avg_time = db.query(func.avg(models.UserSystemUsage.execution_time_ms))\
            .filter(models.UserSystemUsage.user_id == user.id).scalar()
        
        # Calculate error rate
        total_requests = db.query(func.count(models.UserSystemUsage.id))\
            .filter(models.UserSystemUsage.user_id == user.id).scalar() or 1  # avoid div by zero
        
        error_count = db.query(func.count(models.UserSystemUsage.id))\
            .filter(models.UserSystemUsage.user_id == user.id)\
            .filter(models.UserSystemUsage.is_error == True).scalar() or 0
        
        error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0
        
        results.append(UserUsageStats(
            user_id=str(user.id),
            email=user.email,
            total_api_calls=total_api_calls,
            total_data_entries=total_data_entries,
            recent_calls=recent_calls,
            recent_entries=recent_entries,
            avg_execution_time=avg_time,
            error_rate=error_rate
        ))
    
    return results

@router.get("/usage/{user_id}/by-date", response_model=List[UsageByDate])
async def get_user_usage_by_date(
    user_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Get daily usage for a specific user (admin only)"""
    try:
        uuid_obj = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Calculate the date range
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    # Get daily usage counts
    query = db.query(
        func.date_trunc('day', models.UserSystemUsage.timestamp).label('date'),
        func.count(models.UserSystemUsage.id).label('count')
    ).filter(
        models.UserSystemUsage.user_id == user_id,
        models.UserSystemUsage.timestamp >= start_date
    ).group_by(
        func.date_trunc('day', models.UserSystemUsage.timestamp)
    ).order_by(
        func.date_trunc('day', models.UserSystemUsage.timestamp)
    )
    
    results = []
    for row in query:
        results.append(UsageByDate(
            date=row.date.strftime('%Y-%m-%d'),
            count=row.count
        ))
    
    return results

@router.get("/usage/{user_id}/logs", response_model=List[DetailedUsageLog])
async def get_user_usage_logs(
    user_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Get detailed usage logs for a specific user (admin only)"""
    try:
        uuid_obj = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    logs = db.query(models.UserSystemUsage)\
        .filter(models.UserSystemUsage.user_id == user_id)\
        .order_by(desc(models.UserSystemUsage.timestamp))\
        .offset(skip)\
        .limit(limit)\
        .all()
    
    return logs

@router.get("/summary")
async def get_system_summary(
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Get summary statistics of the entire system (admin only)"""
    # Total users
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    
    # Active users in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = db.query(func.count(func.distinct(models.UserSystemUsage.user_id)))\
        .filter(models.UserSystemUsage.timestamp >= thirty_days_ago).scalar() or 0
    
    # Total data entries
    total_entries = db.query(func.count(models.SentimentData.entry_id)).scalar() or 0
    
    # Total API calls
    total_api_calls = db.query(func.sum(models.User.api_calls_count)).scalar() or 0
    
    # Recent API calls (last 24 hours)
    day_ago = datetime.utcnow() - timedelta(days=1)
    recent_calls = db.query(func.count(models.UserSystemUsage.id))\
        .filter(models.UserSystemUsage.timestamp >= day_ago).scalar() or 0
    
    # System error rate
    total_requests = db.query(func.count(models.UserSystemUsage.id)).scalar() or 1
    error_count = db.query(func.count(models.UserSystemUsage.id))\
        .filter(models.UserSystemUsage.is_error == True).scalar() or 0
    error_rate = (error_count / total_requests) * 100 if total_requests > 0 else 0
    
    # Average response time
    avg_time = db.query(func.avg(models.UserSystemUsage.execution_time_ms)).scalar()
    
    return {
        "total_users": total_users,
        "active_users_30d": active_users,
        "total_data_entries": total_entries,
        "total_api_calls": total_api_calls,
        "api_calls_24h": recent_calls,
        "error_rate": error_rate,
        "avg_response_time_ms": avg_time
    }

# API to toggle admin status
@router.put("/users/{user_id}/toggle-admin")
async def toggle_admin_status(
    user_id: str,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(admin_only)
):
    """Toggle admin status for a user (admin only)"""
    try:
        uuid_obj = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent removing admin status from yourself
    if str(user.id) == current_user_id and user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove admin status from yourself"
        )
    
    # Toggle admin status
    user.is_admin = not user.is_admin
    db.commit()
    
    return {"id": str(user.id), "email": user.email, "is_admin": user.is_admin}

@router.post("/add-showcase-data")
async def add_showcase_data(
    db: Session = Depends(get_db),
    _: str = Depends(admin_only)
):
    """Add showcase data for The Nation newspaper and Arise TV channel (admin only)"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import text
        
        # Sample data for "The Nation" newspaper
        nation_data = [
            {
                "id": str(uuid.uuid4()),
                "source_name": "The Nation",
                "platform": "newspaper",
                "title": "President Tinubu Announces New Economic Reforms for 2025",
                "text": "President Bola Tinubu unveiled comprehensive economic reforms aimed at boosting Nigeria's economic growth. The reforms include tax incentives for businesses and infrastructure development plans.",
                "sentiment_label": "positive",
                "sentiment_score": 0.75,
                "date": (datetime.now() - timedelta(hours=2)).isoformat(),
                "url": "https://thenationonlineng.net/economic-reforms-2025",
                "source": "The Nation Online"
            },
            {
                "id": str(uuid.uuid4()),
                "source_name": "The Nation",
                "platform": "newspaper", 
                "title": "Senate Approves Budget for Youth Development Programs",
                "text": "The Nigerian Senate has approved a substantial budget allocation for youth development and job creation programs across the country. This initiative is expected to benefit millions of young Nigerians.",
                "sentiment_label": "positive",
                "sentiment_score": 0.68,
                "date": (datetime.now() - timedelta(hours=6)).isoformat(),
                "url": "https://thenationonlineng.net/youth-budget-approval",
                "source": "The Nation Online"
            },
            {
                "id": str(uuid.uuid4()),
                "source_name": "The Nation",
                "platform": "newspaper",
                "title": "Analysis: Nigeria's Infrastructure Development Progress",
                "text": "A comprehensive analysis of Nigeria's infrastructure development shows steady progress in road construction, power generation, and digital connectivity. However, challenges remain in rural areas.",
                "sentiment_label": "neutral",
                "sentiment_score": 0.45,
                "date": (datetime.now() - timedelta(hours=12)).isoformat(),
                "url": "https://thenationonlineng.net/infrastructure-analysis",
                "source": "The Nation Online"
            }
        ]
        
        # Sample data for "Arise TV" channel
        arise_data = [
            {
                "id": str(uuid.uuid4()),
                "source_name": "Arise TV",
                "platform": "television",
                "title": "Morning Show: President Tinubu's Economic Vision for Nigeria",
                "text": "In today's morning show, experts discussed President Tinubu's economic vision and its potential impact on Nigeria's development. The program featured analysis from leading economists.",
                "sentiment_label": "positive",
                "sentiment_score": 0.72,
                "date": (datetime.now() - timedelta(hours=3)).isoformat(),
                "url": "https://arisemediagroup.com/morning-show",
                "source": "Arise TV"
            },
            {
                "id": str(uuid.uuid4()),
                "source_name": "Arise TV",
                "platform": "television",
                "title": "News at 9: Updates on Government Policies",
                "text": "Tonight's news program covers the latest updates on government policies, including education reforms and healthcare initiatives. The report provides balanced coverage of ongoing developments.",
                "sentiment_label": "neutral",
                "sentiment_score": 0.55,
                "date": (datetime.now() - timedelta(hours=8)).isoformat(),
                "url": "https://arisemediagroup.com/news-9pm",
                "source": "Arise TV"
            },
            {
                "id": str(uuid.uuid4()),
                "source_name": "Arise TV",
                "platform": "television",
                "title": "Special Report: Nigeria's Democratic Progress",
                "text": "A special investigative report examining Nigeria's democratic progress since the last elections. The program highlights achievements in democratic governance and areas for improvement.",
                "sentiment_label": "positive",
                "sentiment_score": 0.65,
                "date": (datetime.now() - timedelta(hours=15)).isoformat(),
                "url": "https://arisemediagroup.com/special-report",
                "source": "Arise TV"
            }
        ]
        
        # Insert the sample data
        all_data = nation_data + arise_data
        
        for item in all_data:
            # Check if item already exists to avoid duplicates
            existing = db.execute(
                text("SELECT id FROM sentiment_data WHERE title = :title"),
                {"title": item["title"]}
            ).fetchone()
            
            if not existing:
                db.execute(
                    text("""
                        INSERT INTO sentiment_data 
                        (id, source_name, platform, title, text, sentiment_label, sentiment_score, date, url, source)
                        VALUES (:id, :source_name, :platform, :title, :text, :sentiment_label, :sentiment_score, :date, :url, :source)
                    """),
                    item
                )
        
        db.commit()
        
        return {
            "status": "success", 
            "message": f"Successfully added showcase data for The Nation and Arise TV",
            "items_added": len(all_data)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding showcase data: {str(e)}") 
