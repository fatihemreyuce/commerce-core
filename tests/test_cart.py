from decimal import Decimal

from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole


def test_bos_sepet_getirilir(client, user_headers):
    resp = client.get("/cart/", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_sepete_urun_eklenir_fiyat_snapshot(client, user_headers, make_variant):
    variant = make_variant(stock=10, base_price="100.00", price_override="80.00")
    resp = client.post(
        "/cart/items",
        headers=user_headers,
        json={"variant_id": str(variant.id), "quantity": 2},
    )
    assert resp.status_code == 201
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 2
    assert Decimal(items[0]["unit_price"]) == Decimal("80.00")  # override kazanır


def test_ayni_variant_tekrar_eklenince_adet_artar(client, user_headers, make_variant):
    variant = make_variant()
    payload = {"variant_id": str(variant.id), "quantity": 1}
    client.post("/cart/items", headers=user_headers, json=payload)
    resp = client.post("/cart/items", headers=user_headers, json=payload)
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 2


def test_olmayan_variant_eklenemez(client, user_headers):
    import uuid
    resp = client.post(
        "/cart/items",
        headers=user_headers,
        json={"variant_id": str(uuid.uuid4()), "quantity": 1},
    )
    assert resp.status_code == 404


def test_adet_guncellenir(client, user_headers, make_variant):
    variant = make_variant()
    add = client.post("/cart/items", headers=user_headers,
                      json={"variant_id": str(variant.id), "quantity": 1})
    item_id = add.json()["items"][0]["id"]
    resp = client.put(f"/cart/items/{item_id}", headers=user_headers, json={"quantity": 5})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["quantity"] == 5


def test_satir_silinir(client, user_headers, make_variant):
    variant = make_variant()
    add = client.post("/cart/items", headers=user_headers,
                      json={"variant_id": str(variant.id), "quantity": 1})
    item_id = add.json()["items"][0]["id"]
    resp = client.delete(f"/cart/items/{item_id}", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_sepet_bosaltilir(client, user_headers, make_variant):
    variant = make_variant()
    client.post("/cart/items", headers=user_headers,
                json={"variant_id": str(variant.id), "quantity": 1})
    resp = client.delete("/cart/", headers=user_headers)
    assert resp.status_code == 204
    getr = client.get("/cart/", headers=user_headers)
    assert getr.json()["items"] == []


def test_giris_yapmadan_sepet_erisilemez(client):
    resp = client.get("/cart/")
    assert resp.status_code in (401, 403)


def test_baska_kullanici_sepet_satirini_guncelleyemez(client, db, user_headers, make_variant):
    # Kullanici A sepete urun ekler
    variant = make_variant()
    add = client.post("/cart/items", headers=user_headers,
                      json={"variant_id": str(variant.id), "quantity": 1})
    item_id = add.json()["items"][0]["id"]

    # Kullanici B olusturulur ve token uretilir
    user2 = User(
        email="user2@test.com",
        full_name="Second User",
        hashed_password=get_password_hash("secret123"),
        role=UserRole.customer,
        is_active=True,
    )
    db.add(user2)
    db.commit()
    db.refresh(user2)
    user2_headers = {"Authorization": f"Bearer {create_access_token(subject=str(user2.id))}"}

    # Kullanici B, Kullanici A'nin sepet satirini guncelleyememeli
    resp = client.put(f"/cart/items/{item_id}", headers=user2_headers, json={"quantity": 99})
    assert resp.status_code == 404


def test_baska_kullanici_sepet_satirini_silemez(client, db, user_headers, make_variant):
    # Kullanici A sepete urun ekler
    variant = make_variant()
    add = client.post("/cart/items", headers=user_headers,
                      json={"variant_id": str(variant.id), "quantity": 1})
    item_id = add.json()["items"][0]["id"]

    # Kullanici B olusturulur ve token uretilir
    user2 = User(
        email="user2@test.com",
        full_name="Second User",
        hashed_password=get_password_hash("secret123"),
        role=UserRole.customer,
        is_active=True,
    )
    db.add(user2)
    db.commit()
    db.refresh(user2)
    user2_headers = {"Authorization": f"Bearer {create_access_token(subject=str(user2.id))}"}

    # Kullanici B, Kullanici A'nin sepet satirini silememeli
    resp = client.delete(f"/cart/items/{item_id}", headers=user2_headers)
    assert resp.status_code == 404
