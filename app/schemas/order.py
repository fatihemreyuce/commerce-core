import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any
from decimal import Decimal
from app.models.order import OrderStatus

class OrderItemResponse(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    model_config = ConfigDict(from_attributes=True)

class OrderCreate(BaseModel):
    shipping_address: Dict[str, Any]

class OrderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatus
    total_amount: Decimal
    shipping_address: Dict[str, Any]
    created_at: datetime
    items: List[OrderItemResponse] = []
    
    model_config = ConfigDict(from_attributes=True)