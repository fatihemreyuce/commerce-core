from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Veritabanı motorunu oluştur (PostgreSQL bağlantısı)
engine = create_engine(settings.DATABASE_URL)

# Veritabanı ile konuşacağımız oturum (session) fabrikası
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tüm modellerimizin miras alacağı temel sınıf
Base = declarative_base()