# app/db.py
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1) DATABASE_URL 우선, 없으면 로컬 기본값
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://rpq_user:rpq_pass@127.0.0.1:5432/rpq_db",
)

# 2) Engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# 3) Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# 4) Declarative Base
Base = declarative_base()


# 5) Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
