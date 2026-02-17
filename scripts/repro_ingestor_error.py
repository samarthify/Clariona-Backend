
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

Base = declarative_base()

class TestModel(Base):
    __tablename__ = 'test_model'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    user_location = Column(String, nullable=True)

def test_upsert_logic():
    print("Simulating upsert logic construction...")
    
    # 1. Normal Insert with user_location provided
    stmt = pg_insert(TestModel).values(
        id=1,
        url="http://example.com/1",
        user_location="Lagos" 
    )
    
    # Check if we can access stmt.excluded['user_location']
    try:
        col = stmt.excluded['user_location']
        print(f"stmt.excluded['user_location'] accessed successfully: {col}")
    except TypeError:
        print("stmt.excluded['user_location'] FAILED (TypeError)")
    except Exception as e:
        print(f"stmt.excluded['user_location'] FAILED: {e}")

    # Check attribute access
    try:
        col = stmt.excluded.user_location
        print(f"stmt.excluded.user_location accessed successfully: {col}")
    except Exception as e:
        print(f"stmt.excluded.user_location FAILED: {e}")

if __name__ == "__main__":
    try:
        test_upsert_logic()
    except Exception as e:
        print(e)
