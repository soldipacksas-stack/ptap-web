import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL de conexión externa de Supabase (reemplaza [YOUR-PASSWORD] con tu contraseña real)
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:*JaviMay2206@db.nbolmzwhwcspydyzfel.supabase.co:5432/postgres"

# SQLAlchemy requiere que la URL empiece por postgresql:// en lugar de postgres://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
