import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.product import ProductResponse


class FavoriteCreate(BaseModel):
    product_id: uuid.UUID


class FavoriteResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    product: ProductResponse

    model_config = ConfigDict(from_attributes=True)
