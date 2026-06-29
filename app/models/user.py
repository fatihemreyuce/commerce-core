import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base

# Kullanıcı rolleri için Enum tanımı
class UserRole(str, enum.Enum):
    customer = "customer"
    admin = "admin"

class User(Base):
    __tablename__ = "users"

    # UUID(as_uuid=True) kullanarak PostgreSQL'in native UUID tipini kullanıyoruz
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(String(150))
    role = Column(Enum(UserRole), default=UserRole.customer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))