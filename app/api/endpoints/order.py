from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_permission
from app.core.permissions import Permission, has_permission
from app.models.user import User, UserRole
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import ProductVariant
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate

router = APIRouter()


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kullanıcının sepetinden sipariş oluşturur. Stok kontrol edilir ama düşürülmez."""
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    items = db.query(CartItem).filter(CartItem.cart_id == cart.id).all() if cart else []
    if not items:
        raise HTTPException(status_code=400, detail="Sepetiniz boş.")

    total = Decimal("0.00")
    for it in items:
        variant = db.query(ProductVariant).filter(ProductVariant.id == it.variant_id).first()
        if not variant:
            raise HTTPException(status_code=400, detail="Sepetteki bir ürün artık mevcut değil.")
        if variant.stock_qty < it.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Yetersiz stok: {variant.sku} (mevcut: {variant.stock_qty}).",
            )
        total += it.unit_price * it.quantity

    order = Order(
        user_id=current_user.id,
        status=OrderStatus.pending,
        total_amount=total,
        shipping_address=order_in.shipping_address,
    )
    db.add(order)
    db.flush()  # order.id üretilsin

    for it in items:
        db.add(
            OrderItem(
                order_id=order.id,
                variant_id=it.variant_id,
                quantity=it.quantity,
                unit_price=it.unit_price,
            )
        )

    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    db.refresh(order)
    return order


@router.get("/", response_model=List[OrderResponse])
def my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Kullanıcının kendi siparişlerini listeler."""
    return (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )


@router.get("/admin/all", response_model=List[OrderResponse])
def all_orders(db: Session = Depends(get_db), current_admin: User = Depends(require_permission(Permission.ORDER_READ_ALL))):
    """Tüm siparişleri listeler. Sadece Adminler."""
    return db.query(Order).order_by(Order.created_at.desc()).all()


@router.get("/{order_id}", response_model=OrderResponse)
def order_detail(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sipariş detayı. Sahibi veya admin görebilir."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı.")
    if order.user_id != current_user.id and not has_permission(
        current_user.role, Permission.ORDER_READ_ALL
    ):
        raise HTTPException(status_code=403, detail="Bu siparişe erişim yetkiniz yok.")
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_permission(Permission.ORDER_UPDATE_STATUS)),
):
    """Sipariş durumunu günceller. Sadece Adminler."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı.")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order
