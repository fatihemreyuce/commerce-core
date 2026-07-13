from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.product import Product, ProductVariant
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductVariantCreate,
    ProductVariantResponse,
)
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: ProductCreate, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_permission(Permission.PRODUCT_MANAGE)) # SADECE ADMİNLER
):
    """Yeni bir ürün oluşturur. Sadece Adminler yapabilir."""
    
    # Slug (URL adı) benzersiz mi kontrol edelim
    existing_product = db.query(Product).filter(Product.slug == product_in.slug).first()
    if existing_product:
        raise HTTPException(status_code=400, detail="Bu URL (slug) ile başka bir ürün zaten kayıtlı.")
    
    db_product = Product(**product_in.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.get("/", response_model=List[ProductResponse])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Sistemdeki tüm ürünleri ve onlara bağlı varyantları listeler. (Herkese Açık)"""
    return db.query(Product).offset(skip).limit(limit).all()

@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: str, db: Session = Depends(get_db)):
    """Belirli bir ürünü detayları ve varyantlarıyla getirir. (Herkese Açık)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
    return product

@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_permission(Permission.PRODUCT_MANAGE)) # SADECE ADMİNLER
):
    """Sistemden bir ürünü siler. Sadece Adminler yapabilir."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")
        
    db.delete(product)
    db.commit()
    return None


@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    product_id: str,
    variant_in: ProductVariantCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_permission(Permission.PRODUCT_MANAGE)),
):
    """Bir ürüne varyant (renk/beden/SKU/stok) ekler. Sadece Adminler."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")

    existing = db.query(ProductVariant).filter(ProductVariant.sku == variant_in.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu SKU zaten kullanımda.")

    db_variant = ProductVariant(product_id=product.id, **variant_in.model_dump())
    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)
    return db_variant


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    variant_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_permission(Permission.PRODUCT_MANAGE)),
):
    """Bir varyantı siler. Sadece Adminler."""
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Varyant bulunamadı.")
    db.delete(variant)
    db.commit()
    return None
