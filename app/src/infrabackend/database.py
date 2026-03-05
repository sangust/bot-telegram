from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.src.infrabackend.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,           
    max_overflow=20,        
    pool_recycle=3600,     
    pool_pre_ping=True,   
    pool_timeout=30,       
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,   
    autoflush=False,    
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Verifica se o banco está acessível. Usado no health check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False