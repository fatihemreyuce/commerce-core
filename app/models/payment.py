import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.session import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), unique=True, nullable=False)
    paytr_token = Column(Text, nullable=True)
    paytr_status = Column(String(30), default="waiting")
    amount = Column(Numeric(10, 2), nullable=False)
    raw_webhook = Column(JSONB, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="payment")