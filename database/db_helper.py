# /database/db_helper.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager

# Database URL (adjust based on your database configuration)
DATABASE_URL = "sqlite:///database.db"

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

async def init_db():
    print("Connecting to the database...")
    Base.metadata.create_all(bind=engine)

async def close_db():
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

