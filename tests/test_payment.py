import base64
import hashlib
import hmac

from app.core.config import settings
from app.api.endpoints import payment as payment_endpoint


def _make_order(client, user_headers, make_variant, stock=10, qty=2, price="100.00"):
    variant = make_variant(stock=stock, base_price=price)
    client.post("/cart/items", headers=user_headers,
                json={"variant_id": str(variant.id), "quantity": qty})
    order = client.post("/orders/", headers=user_headers,
                        json={"shipping_address": {"address": "Adres", "phone": "555"}}).json()
    return variant, order


def _callback_hash(merchant_oid, status, total_amount):
    return base64.b64encode(
        hmac.new(
            settings.PAYTR_MERCHANT_KEY.encode(),
            (merchant_oid + settings.PAYTR_MERCHANT_SALT + status + total_amount).encode(),
            hashlib.sha256,
        ).digest()
    ).decode()


def test_odeme_baslatilir(client, user_headers, make_variant, monkeypatch):
    monkeypatch.setattr(
        payment_endpoint.paytr, "generate_iframe_token", lambda **kwargs: "fake-token-xyz"
    )
    _, order = _make_order(client, user_headers, make_variant)
    resp = client.post(f"/payments/start/{order['id']}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["iframe_token"] == "fake-token-xyz"


def test_baska_kullanicinin_siparisine_odeme_baslatilamaz(client, user_headers, admin_headers, make_variant, monkeypatch):
    monkeypatch.setattr(
        payment_endpoint.paytr, "generate_iframe_token", lambda **kwargs: "t"
    )
    _, order = _make_order(client, user_headers, make_variant)
    # admin farklı kullanıcı; order user'a ait → 403
    resp = client.post(f"/payments/start/{order['id']}", headers=admin_headers)
    assert resp.status_code == 403


def test_webhook_basarili_stok_duser_ve_siparis_paid(client, db, user_headers, make_variant, monkeypatch):
    from app.models.product import ProductVariant
    from app.models.order import Order
    monkeypatch.setattr(
        payment_endpoint.paytr, "generate_iframe_token", lambda **kwargs: "t"
    )
    variant, order = _make_order(client, user_headers, make_variant, stock=10, qty=3)
    client.post(f"/payments/start/{order['id']}", headers=user_headers)

    import uuid
    merchant_oid = uuid.UUID(order["id"]).hex
    total_amount = "30000"  # önemi yok, hash tutarlı olsun yeter
    h = _callback_hash(merchant_oid, "success", total_amount)
    resp = client.post(
        "/payments/callback",
        data={"merchant_oid": merchant_oid, "status": "success",
              "total_amount": total_amount, "hash": h},
    )
    assert resp.status_code == 200
    assert resp.text == "OK"

    db.expire_all()
    fresh_variant = db.query(ProductVariant).filter(ProductVariant.id == variant.id).first()
    assert fresh_variant.stock_qty == 7  # 10 - 3
    fresh_order = db.query(Order).filter(Order.id == uuid.UUID(order["id"])).first()
    assert fresh_order.status.value == "paid"


def test_webhook_gecersiz_hash_islem_yapmaz(client, db, user_headers, make_variant, monkeypatch):
    from app.models.product import ProductVariant
    monkeypatch.setattr(
        payment_endpoint.paytr, "generate_iframe_token", lambda **kwargs: "t"
    )
    variant, order = _make_order(client, user_headers, make_variant, stock=10, qty=3)
    client.post(f"/payments/start/{order['id']}", headers=user_headers)

    import uuid
    merchant_oid = uuid.UUID(order["id"]).hex
    resp = client.post(
        "/payments/callback",
        data={"merchant_oid": merchant_oid, "status": "success",
              "total_amount": "30000", "hash": "yanlis"},
    )
    assert resp.status_code == 200
    assert "PAYTR notification failed" in resp.text
    db.expire_all()
    fresh = db.query(ProductVariant).filter(ProductVariant.id == variant.id).first()
    assert fresh.stock_qty == 10  # değişmemeli


def test_webhook_basarisiz_odeme_stok_dokunmaz(client, db, user_headers, make_variant, monkeypatch):
    from app.models.product import ProductVariant
    monkeypatch.setattr(
        payment_endpoint.paytr, "generate_iframe_token", lambda **kwargs: "t"
    )
    variant, order = _make_order(client, user_headers, make_variant, stock=10, qty=3)
    client.post(f"/payments/start/{order['id']}", headers=user_headers)

    import uuid
    merchant_oid = uuid.UUID(order["id"]).hex
    h = _callback_hash(merchant_oid, "failed", "30000")
    resp = client.post(
        "/payments/callback",
        data={"merchant_oid": merchant_oid, "status": "failed",
              "total_amount": "30000", "hash": h},
    )
    assert resp.status_code == 200
    assert resp.text == "OK"
    db.expire_all()
    fresh = db.query(ProductVariant).filter(ProductVariant.id == variant.id).first()
    assert fresh.stock_qty == 10
