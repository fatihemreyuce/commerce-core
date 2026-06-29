import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from decimal import Decimal

class ProductVariantBase(BaseModel):
    color: Optional[str] = None
    size: Optional[str] = None
    sku: str
    price_override: Optional[Decimal] = None
    stock_qty: int = 0
    images: List[str] = []

class ProductVariantCreate(ProductVariantBase):
    pass

class ProductVariantResponse(ProductVariantBase):
    id: uuid.UUID
    product_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

class ProductBase(BaseModel):
    category_id: int
    name: str
    slug: str
    description: Optional[str] = None
    base_price: Decimal
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: uuid.UUID
    created_at: datetime
    variants: List[ProductVariantResponse] = []

    model_config = ConfigDict(from_attributes=True)