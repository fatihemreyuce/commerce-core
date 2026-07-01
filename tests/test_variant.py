import uuid


def _create_product(db):
    from decimal import Decimal
    from app.models.category import Category
    from app.models.product import Product
    cat = Category(name="Elektronik", slug="elektronik")
    db.add(cat); db.commit(); db.refresh(cat)
    prod = Product(category_id=cat.id, name="Telefon", slug="telefon", base_price=Decimal("5000.00"))
    db.add(prod); db.commit(); db.refresh(prod)
    return prod


def test_admin_variant_olusturabilir(client, db, admin_headers):
    prod = _create_product(db)
    resp = client.post(
        f"/products/{prod.id}/variants",
        headers=admin_headers,
        json={"color": "Siyah", "size": "128GB", "sku": "TEL-SYH-128", "stock_qty": 15},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["sku"] == "TEL-SYH-128"
    assert body["stock_qty"] == 15
    assert body["product_id"] == str(prod.id)


def test_normal_kullanici_variant_olusturamaz(client, db, user_headers):
    prod = _create_product(db)
    resp = client.post(
        f"/products/{prod.id}/variants",
        headers=user_headers,
        json={"sku": "X-1", "stock_qty": 1},
    )
    assert resp.status_code == 403


def test_olmayan_urune_variant_eklenemez(client, admin_headers):
    resp = client.post(
        f"/products/{uuid.uuid4()}/variants",
        headers=admin_headers,
        json={"sku": "X-2", "stock_qty": 1},
    )
    assert resp.status_code == 404


def test_ayni_sku_iki_kez_eklenemez(client, db, admin_headers):
    prod = _create_product(db)
    payload = {"sku": "DUP-1", "stock_qty": 1}
    client.post(f"/products/{prod.id}/variants", headers=admin_headers, json=payload)
    resp = client.post(f"/products/{prod.id}/variants", headers=admin_headers, json=payload)
    assert resp.status_code == 400
