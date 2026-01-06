from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file located in config directory (if exists)
try:
    from src.config.path_manager import PathManager
    path_manager = PathManager()
    env_path = path_manager.config_dir / '.env'
except Exception:
    # Fallback if PathManager not available
    env_path = Path(__file__).parent.parent.parent / 'config' / '.env'

if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Also load from system environment variables (for Railway deployment)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Default to local SQLite for Railway
    DATABASE_URL = "sqlite:///./sentiment_analysis_local.db"

# Load ConfigManager for database pool settings
try:
    from src.config.config_manager import ConfigManager
    config_manager = ConfigManager()
    pool_size = config_manager.get_int("database.pool_size", 30)
    max_overflow = config_manager.get_int("database.max_overflow", 20)
    pool_recycle = config_manager.get_int("database.pool_recycle_seconds", 3600)
    pool_timeout = config_manager.get_int("database.pool_timeout_seconds", 60)
except Exception as e:
    # Fallback to defaults if ConfigManager not available
    print(f"Warning: Could not load ConfigManager, using default database pool settings: {e}")
    pool_size = 30
    max_overflow = 20
    pool_recycle = 3600
    pool_timeout = 60

# Configure the engine with optimized connection pool for 32 vCPU instance
# Total workers: 12 (collectors) + 18 (sentiment) + 10 (location) = 40 workers max
# Pool size should accommodate this + overhead for API requests
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # Check connections before use
        pool_recycle=pool_recycle,       # Recycle connections (configurable)
        pool_size=pool_size,            # Base connection pool (configurable)
        max_overflow=max_overflow,         # Extra connections for peak load (configurable)
        pool_timeout=pool_timeout,         # Wait for connection (configurable)
        echo=False               # Disable SQL echo for performance
    )
except Exception as e:
    print(f"Error creating database engine: {e}")
    raise

# Configure the session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models (can be imported from models.py if preferred)
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create tables (optional - use Alembic for migrations)
def create_tables():
    # Import your models here before calling create_all
    from . import models
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        print(f"Error creating tables: {e}")
        print("Ensure the database server is running and the DATABASE_URL is correct.")
        return False

# Create tables immediately when this module is imported (only if database doesn't exist)
import os
db_file_path = DATABASE_URL.replace("sqlite:///", "").replace("./", "")
if not os.path.exists(db_file_path):
    try:
        create_tables()
    except Exception as e:
        print(f"Failed to create tables on startup: {e}") 
