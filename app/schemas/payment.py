import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from decimal import Decimal

class PaymentResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    paytr_token: Optional[str] = None
    paytr_status: str
    amount: Decimal
    paid_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class PaymentStartResponse(BaseModel):
    iframe_token: str