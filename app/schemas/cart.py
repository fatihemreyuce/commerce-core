import uuid
from pydantic import BaseModel, ConfigDict
from typing import List
from decimal import Decimal

class CartItemCreate(BaseModel):
    variant_id: uuid.UUID
    quantity: int = 1

class CartItemResponse(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    quantity: int
    unit_price: Decimal

    model_config = ConfigDict(from_attributes=True)

class CartResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    items: List[CartItemResponse] = []

    model_config = ConfigDict(from_attributes=True)