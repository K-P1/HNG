from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

try:
    engine = create_engine(settings.DATABASE_URL)
except ModuleNotFoundError as e:
    # Fallback to a local sqlite file
    print(f"Warning: failed to load DB driver for {settings.DATABASE_URL}: {e}. Falling back to sqlite:///./dev.db")
    engine = create_engine("sqlite:///./dev.db")
except Exception:
    engine = create_engine("sqlite:///./dev.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
