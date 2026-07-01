from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.cart import Cart, CartItem
from app.models.product import ProductVariant
from app.schemas.cart import CartResponse, CartItemCreate, CartItemUpdate
from app.utils.pricing import effective_unit_price

router = APIRouter()


def _get_or_create_cart(db: Session, user: User) -> Cart:
    cart = db.query(Cart).filter(Cart.user_id == user.id).first()
    if not cart:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


@router.get("/", response_model=CartResponse)
def get_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Kullanıcının sepetini getirir (yoksa oluşturur)."""
    return _get_or_create_cart(db, current_user)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    item_in: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sepete varyant ekler. Aynı varyant zaten varsa adedini artırır."""
    if item_in.quantity < 1:
        raise HTTPException(status_code=400, detail="Adet en az 1 olmalı.")

    variant = db.query(ProductVariant).filter(ProductVariant.id == item_in.variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Varyant bulunamadı.")

    cart = _get_or_create_cart(db, current_user)
    existing = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id, CartItem.variant_id == variant.id)
        .first()
    )
    if existing:
        existing.quantity += item_in.quantity
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                variant_id=variant.id,
                quantity=item_in.quantity,
                unit_price=effective_unit_price(variant),
            )
        )
    db.commit()
    db.refresh(cart)
    return cart


@router.put("/items/{item_id}", response_model=CartResponse)
def update_item(
    item_id: str,
    item_in: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sepet satırının adedini günceller."""
    cart = _get_or_create_cart(db, current_user)
    item = (
        db.query(CartItem)
        .filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sepet satırı bulunamadı.")
    if item_in.quantity < 1:
        raise HTTPException(status_code=400, detail="Adet en az 1 olmalı.")
    item.quantity = item_in.quantity
    db.commit()
    db.refresh(cart)
    return cart


@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sepetten bir satırı siler."""
    cart = _get_or_create_cart(db, current_user)
    item = (
        db.query(CartItem)
        .filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Sepet satırı bulunamadı.")
    db.delete(item)
    db.commit()
    db.refresh(cart)
    return cart


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Sepeti tamamen boşaltır."""
    cart = _get_or_create_cart(db, current_user)
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    return None
