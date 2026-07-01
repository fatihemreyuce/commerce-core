import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment
from app.models.product import ProductVariant
from app.schemas.payment import PaymentStartResponse
from app.utils import paytr

router = APIRouter()


@router.post("/start/{order_id}", response_model=PaymentStartResponse)
def start_payment(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bir sipariş için PayTR iframe token üretir ve Payment kaydını hazırlar."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı.")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu siparişe erişim yetkiniz yok.")
    if order.status != OrderStatus.pending:
        raise HTTPException(status_code=400, detail="Bu sipariş için ödeme başlatılamaz.")

    items = []
    for oi in order.items:
        variant = db.query(ProductVariant).filter(ProductVariant.id == oi.variant_id).first()
        name = variant.product.name if variant and variant.product else "Ürün"
        items.append({"name": name, "unit_price": oi.unit_price, "quantity": oi.quantity})

    addr = order.shipping_address or {}
    token = paytr.generate_iframe_token(
        merchant_oid=order.id.hex,
        email=current_user.email,
        amount=order.total_amount,
        user_ip=request.client.host if request.client else "0.0.0.0",
        user_name=current_user.full_name or addr.get("name", "Müşteri"),
        user_address=addr.get("address", "-"),
        user_phone=addr.get("phone", "-"),
        items=items,
    )

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        payment = Payment(order_id=order.id, amount=order.total_amount)
        db.add(payment)
    payment.paytr_token = token
    payment.paytr_status = "waiting"
    db.commit()
    return PaymentStartResponse(iframe_token=token)


@router.post("/callback")
async def payment_callback(request: Request, db: Session = Depends(get_db)):
    """PayTR webhook. Hash doğrular; başarılı ödemede stok düşer, sipariş 'paid' olur."""
    form = await request.form()
    post_data = dict(form)

    if not paytr.verify_callback_hash(post_data):
        return Response(content="PAYTR notification failed: bad hash", media_type="text/plain")

    merchant_oid = post_data.get("merchant_oid", "")
    try:
        order_id = uuid.UUID(hex=merchant_oid)
    except ValueError:
        return Response(content="OK", media_type="text/plain")

    order = db.query(Order).filter(Order.id == order_id).first()
    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
    if not order or not payment:
        return Response(content="OK", media_type="text/plain")

    payment.raw_webhook = post_data

    if post_data.get("status") == "success":
        if payment.paytr_status != "success":  # idempotent — iki kez düşürme
            payment.paytr_status = "success"
            payment.paid_at = datetime.now(timezone.utc)
            order.status = OrderStatus.paid
            for oi in order.items:
                variant = (
                    db.query(ProductVariant)
                    .filter(ProductVariant.id == oi.variant_id)
                    .first()
                )
                if variant:
                    variant.stock_qty = max(0, variant.stock_qty - oi.quantity)
    else:
        payment.paytr_status = "failed"

    db.commit()
    return Response(content="OK", media_type="text/plain")
