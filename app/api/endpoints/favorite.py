from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.favorite import Favorite
from app.models.product import Product
from app.models.user import User
from app.schemas.favorite import FavoriteCreate, FavoriteResponse

router = APIRouter()


@router.post("/", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def add_favorite(
    fav_in: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bir ürünü kullanıcının favorilerine ekler."""
    product = db.query(Product).filter(Product.id == fav_in.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı.")

    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.product_id == fav_in.product_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Bu ürün zaten favorilerinizde.")

    fav = Favorite(user_id=current_user.id, product_id=fav_in.product_id)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


@router.get("/", response_model=List[FavoriteResponse])
def list_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kullanıcının favorilerini ürün detaylarıyla listeler."""
    return (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bir ürünü kullanıcının favorilerinden çıkarır."""
    fav = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.product_id == product_id)
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favori bulunamadı.")
    db.delete(fav)
    db.commit()
    return None
