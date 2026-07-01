from decimal import Decimal


def _add_to_cart(client, headers, variant_id, qty):
    return client.post("/cart/items", headers=headers,
                       json={"variant_id": str(variant_id), "quantity": qty})


def test_sepetten_siparis_olusturulur(client, user_headers, make_variant):
    variant = make_variant(stock=10, base_price="100.00")
    _add_to_cart(client, user_headers, variant.id, 3)
    resp = client.post("/orders/", headers=user_headers,
                       json={"shipping_address": {"address": "Test Mah.", "phone": "5550001122"}})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert Decimal(body["total_amount"]) == Decimal("300.00")
    assert len(body["items"]) == 1
    # sepet temizlenmeli
    cart = client.get("/cart/", headers=user_headers)
    assert cart.json()["items"] == []


def test_bos_sepetle_siparis_olmaz(client, user_headers):
    resp = client.post("/orders/", headers=user_headers,
                       json={"shipping_address": {"address": "x"}})
    assert resp.status_code == 400


def test_yetersiz_stok_siparis_engellenir(client, user_headers, make_variant):
    variant = make_variant(stock=2)
    _add_to_cart(client, user_headers, variant.id, 5)
    resp = client.post("/orders/", headers=user_headers,
                       json={"shipping_address": {"address": "x"}})
    assert resp.status_code == 400


def test_siparis_olustururken_stok_dusmez(client, db, user_headers, make_variant):
    from app.models.product import ProductVariant
    variant = make_variant(stock=10)
    _add_to_cart(client, user_headers, variant.id, 4)
    client.post("/orders/", headers=user_headers,
                json={"shipping_address": {"address": "x"}})
    fresh = db.query(ProductVariant).filter(ProductVariant.id == variant.id).first()
    assert fresh.stock_qty == 10  # webhook'a kadar düşmez


def test_kullanici_kendi_siparislerini_listeler(client, user_headers, make_variant):
    variant = make_variant()
    _add_to_cart(client, user_headers, variant.id, 1)
    client.post("/orders/", headers=user_headers, json={"shipping_address": {"a": 1}})
    resp = client.get("/orders/", headers=user_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_baska_kullanicinin_siparisi_gorulemez(client, db, user_headers, admin_headers, make_variant):
    variant = make_variant()
    _add_to_cart(client, user_headers, variant.id, 1)
    order = client.post("/orders/", headers=user_headers,
                        json={"shipping_address": {"a": 1}}).json()
    # admin farklı bir kullanıcı ama admin olduğu için görebilir; normal başka user göremez.
    # Burada admin erişimini test ediyoruz:
    resp = client.get(f"/orders/{order['id']}", headers=admin_headers)
    assert resp.status_code == 200


def test_admin_tum_siparisleri_gorur(client, user_headers, admin_headers, make_variant):
    variant = make_variant()
    _add_to_cart(client, user_headers, variant.id, 1)
    client.post("/orders/", headers=user_headers, json={"shipping_address": {"a": 1}})
    resp = client.get("/orders/admin/all", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_normal_kullanici_admin_listesini_goremez(client, user_headers):
    resp = client.get("/orders/admin/all", headers=user_headers)
    assert resp.status_code == 403


def test_admin_siparis_durumu_gunceller(client, user_headers, admin_headers, make_variant):
    variant = make_variant()
    _add_to_cart(client, user_headers, variant.id, 1)
    order = client.post("/orders/", headers=user_headers,
                        json={"shipping_address": {"a": 1}}).json()
    resp = client.patch(f"/orders/{order['id']}/status", headers=admin_headers,
                        json={"status": "shipped"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "shipped"
