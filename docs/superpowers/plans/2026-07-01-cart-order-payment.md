# Sepet → Sipariş → Ödeme Akışı — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kullanıcının ürün varyantı seçip sepete eklemesinden PayTR ile ödeme onayına kadar olan tam e-ticaret akışını FastAPI backend'ine eklemek.

**Architecture:** Mevcut katmanlı yapı korunur (models / schemas / api.endpoints / utils). Sepet ve sipariş için `get_current_user`, admin işlemleri için `require_admin` guard'ları kullanılır. Fiyatlar sepete/siparişe **snapshot** yazılır. Stok, ödeme webhook'u onaylanınca düşer. PayTR entegrasyonu `app/utils/paytr.py` içinde HMAC-SHA256 token/hash mantığıyla yapılır; HTTP çağrısı `requests` ile.

**Tech Stack:** Python, FastAPI 0.138, SQLAlchemy 2.0, PostgreSQL, Pydantic v2, PayTR iFrame API, pytest + httpx.

## Global Constraints

- Postgres-özel tipler kullanılıyor (UUID, JSONB, ARRAY) — testler **PostgreSQL** ister; SQLite ile çalışmaz.
- Para birimi: DB'de `Numeric(10,2)` (TL). PayTR'ye giden tutar **kuruş** (TL × 100, integer).
- Hata mesajları Türkçe, mevcut endpoint'lerdeki üslupla tutarlı.
- Fiyatlama kuralı her yerde aynı: `variant.price_override` doluysa o, değilse `variant.product.base_price`.
- Ödeme webhook'u PayTR'ye **her durumda** düz metin `OK` döndürmeli (hash geçersizse `PAYTR notification failed...`).
- Yeni bağımlılıklar: `requests` (runtime), `pytest` + `httpx` (test).
- Router prefix'leri: `/cart`, `/orders`, `/payments`. Variant endpoint'leri mevcut `/products` router'ına eklenir.

## Dosya Yapısı

**Oluşturulacak:**
- `app/utils/pricing.py` — tek sorumluluk: efektif birim fiyat hesabı.
- `app/api/endpoints/cart.py` — sepet endpoint'leri.
- `app/api/endpoints/order.py` — sipariş endpoint'leri.
- `app/api/endpoints/payment.py` — ödeme başlatma + webhook.
- `tests/conftest.py` — test DB, fixture'lar, auth header'ları, katalog factory.
- `tests/test_pricing.py`, `tests/test_variant.py`, `tests/test_cart.py`, `tests/test_order.py`, `tests/test_paytr.py`, `tests/test_payment.py`.

**Değiştirilecek:**
- `requirements.txt` — `requests`, `pytest`, `httpx`.
- `app/core/config.py` — `PAYTR_OK_URL`, `PAYTR_FAIL_URL` (varsayılanlı).
- `app/utils/paytr.py` — boş dosya doldurulur.
- `app/api/endpoints/product.py` — variant create/delete eklenir.
- `app/schemas/cart.py` — `CartItemUpdate` eklenir.
- `app/schemas/order.py` — `OrderStatusUpdate` eklenir.
- `app/main.py` — cart/order/payment router'ları register edilir.

---

## Task 1: Temel altyapı (bağımlılıklar, config, fiyat util'i, test iskeleti)

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/config.py`
- Create: `app/utils/pricing.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_pricing.py`

**Interfaces:**
- Produces: `app.utils.pricing.effective_unit_price(variant) -> Decimal`
- Produces (conftest fixtures): `db` (Session), `client` (TestClient), `normal_user` (User), `admin_user` (User), `user_headers` (dict), `admin_headers` (dict), `make_variant(stock=10, base_price="100.00", price_override=None, sku=None) -> ProductVariant`

- [ ] **Step 1: requirements.txt'e bağımlılıkları ekle**

`requirements.txt` sonuna ekle:

```
requests==2.32.3
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: config'e PayTR ok/fail URL'lerini ekle**

`app/core/config.py` içinde `PAYTR_CALLBACK_URL: str` satırının altına ekle:

```python
    PAYTR_OK_URL: str = "https://yourdomain.com/payment/success"
    PAYTR_FAIL_URL: str = "https://yourdomain.com/payment/fail"
```

- [ ] **Step 3: Failing test yaz (fiyatlama)**

`tests/__init__.py` boş dosya oluştur. `tests/test_pricing.py`:

```python
from decimal import Decimal
from app.models.product import Product, ProductVariant
from app.utils.pricing import effective_unit_price


def test_price_override_kazanir():
    product = Product(base_price=Decimal("100.00"))
    variant = ProductVariant(price_override=Decimal("80.00"))
    variant.product = product
    assert effective_unit_price(variant) == Decimal("80.00")


def test_override_yoksa_base_price():
    product = Product(base_price=Decimal("100.00"))
    variant = ProductVariant(price_override=None)
    variant.product = product
    assert effective_unit_price(variant) == Decimal("100.00")
```

- [ ] **Step 4: Testi çalıştır, fail görmeli**

Run: `pytest tests/test_pricing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.pricing'`

- [ ] **Step 5: pricing util'ini yaz**

`app/utils/pricing.py`:

```python
from decimal import Decimal


def effective_unit_price(variant) -> Decimal:
    """Variant'ın efektif birim fiyatı: override doluysa o, değilse ürünün base_price'ı."""
    if variant.price_override is not None:
        return variant.price_override
    return variant.product.base_price
```

- [ ] **Step 6: Testi çalıştır, geçmeli**

Run: `pytest tests/test_pricing.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: conftest.py yaz (test DB + fixture'lar)**

`tests/conftest.py`:

```python
import os
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  — tüm modelleri Base'e kaydeder
from app.db.session import Base
from app.core.deps import get_db
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.product import Product, ProductVariant
from app.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/ecommerce_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    # Her testten önce tüm tabloları temizle (FK sırasına göre tersten)
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def normal_user(db):
    user = User(
        email="user@test.com",
        full_name="Test User",
        hashed_password=get_password_hash("secret123"),
        role=UserRole.customer,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    user = User(
        email="admin@test.com",
        full_name="Admin",
        hashed_password=get_password_hash("secret123"),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_headers(normal_user):
    token = create_access_token(subject=str(normal_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user):
    token = create_access_token(subject=str(admin_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_variant(db):
    def _make(stock=10, base_price="100.00", price_override=None, sku=None):
        cat = Category(name=f"Cat {uuid.uuid4().hex[:6]}", slug=f"cat-{uuid.uuid4().hex[:6]}")
        db.add(cat)
        db.commit()
        db.refresh(cat)
        product = Product(
            category_id=cat.id,
            name="Test Product",
            slug=f"prod-{uuid.uuid4().hex[:8]}",
            base_price=Decimal(base_price),
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        variant = ProductVariant(
            product_id=product.id,
            sku=sku or f"SKU-{uuid.uuid4().hex[:8]}",
            stock_qty=stock,
            price_override=Decimal(price_override) if price_override else None,
        )
        db.add(variant)
        db.commit()
        db.refresh(variant)
        return variant

    return _make
```

- [ ] **Step 8: conftest smoke — root endpoint testi**

`tests/test_pricing.py` sonuna ekle:

```python
def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()
```

- [ ] **Step 9: Tüm testleri çalıştır**

Run: `pytest tests/ -v`
Expected: PASS (3 passed). Not: PostgreSQL test veritabanı çalışıyor olmalı; yoksa `TEST_DATABASE_URL` ile göster.

- [ ] **Step 10: Commit**

```bash
git add requirements.txt app/core/config.py app/utils/pricing.py tests/
git commit -m "feat: test altyapisi, fiyat util'i ve PayTR url ayarlari"
```

---

## Task 2: Variant oluşturma/silme endpoint'leri

**Files:**
- Modify: `app/api/endpoints/product.py`
- Test: `tests/test_variant.py`

**Interfaces:**
- Consumes: `require_admin`, `get_db`, `ProductVariantCreate`, `ProductVariantResponse`
- Produces: `POST /products/{product_id}/variants`, `DELETE /products/variants/{variant_id}`

- [ ] **Step 1: Failing test yaz**

`tests/test_variant.py`:

```python
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
```

- [ ] **Step 2: Testi çalıştır, fail görmeli**

Run: `pytest tests/test_variant.py -v`
Expected: FAIL — 404 (endpoint yok) / route bulunamıyor.

- [ ] **Step 3: Variant endpoint'lerini ekle**

`app/api/endpoints/product.py` — import satırlarını güncelle ve dosya sonuna endpoint'leri ekle. Import bloğunu şu hale getir:

```python
from app.models.product import Product, ProductVariant
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductVariantCreate,
    ProductVariantResponse,
)
```

Dosyanın **sonuna** ekle:

```python
@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    product_id: str,
    variant_in: ProductVariantCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
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
    current_admin: User = Depends(require_admin),
):
    """Bir varyantı siler. Sadece Adminler."""
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Varyant bulunamadı.")
    db.delete(variant)
    db.commit()
    return None
```

- [ ] **Step 4: Testi çalıştır, geçmeli**

Run: `pytest tests/test_variant.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/api/endpoints/product.py tests/test_variant.py
git commit -m "feat: variant olusturma ve silme endpoint'leri"
```

---

## Task 3: Sepet endpoint'leri

**Files:**
- Modify: `app/schemas/cart.py`
- Create: `app/api/endpoints/cart.py`
- Modify: `app/main.py`
- Test: `tests/test_cart.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_db`, `effective_unit_price`, `CartResponse`, `CartItemCreate`
- Produces: `CartItemUpdate {quantity:int}` schema; router `cart.router` with
  `GET /cart/`, `POST /cart/items`, `PUT /cart/items/{item_id}`, `DELETE /cart/items/{item_id}`, `DELETE /cart/`

- [ ] **Step 1: CartItemUpdate şemasını ekle**

`app/schemas/cart.py` içinde `CartItemCreate` sınıfının altına ekle:

```python
class CartItemUpdate(BaseModel):
    quantity: int
```

- [ ] **Step 2: Failing test yaz**

`tests/test_cart.py`:

```python
from decimal import Decimal


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
```

- [ ] **Step 3: Testi çalıştır, fail görmeli**

Run: `pytest tests/test_cart.py -v`
Expected: FAIL — route yok (404).

- [ ] **Step 4: cart.py endpoint'lerini yaz**

`app/api/endpoints/cart.py`:

```python
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
```

- [ ] **Step 5: cart router'ını main.py'ye ekle**

`app/main.py` — import satırını güncelle:

```python
from app.api.endpoints import auth, category, product, cart
```

Router register bloğuna ekle (product satırının altına):

```python
app.include_router(cart.router, prefix="/cart", tags=["Sepet"])
```

- [ ] **Step 6: Testi çalıştır, geçmeli**

Run: `pytest tests/test_cart.py -v`
Expected: PASS (8 passed)

- [ ] **Step 7: Commit**

```bash
git add app/schemas/cart.py app/api/endpoints/cart.py app/main.py tests/test_cart.py
git commit -m "feat: sepet endpoint'leri (ekle/guncelle/sil/bosalt)"
```

---

## Task 4: Sipariş endpoint'leri

**Files:**
- Modify: `app/schemas/order.py`
- Create: `app/api/endpoints/order.py`
- Modify: `app/main.py`
- Test: `tests/test_order.py`

**Interfaces:**
- Consumes: `get_current_user`, `require_admin`, `get_db`, `OrderCreate`, `OrderResponse`, `Cart`, `CartItem`, `ProductVariant`
- Produces: `OrderStatusUpdate {status: OrderStatus}` schema; router `order.router` with
  `POST /orders/`, `GET /orders/`, `GET /orders/admin/all`, `GET /orders/{order_id}`, `PATCH /orders/{order_id}/status`

- [ ] **Step 1: OrderStatusUpdate şemasını ekle**

`app/schemas/order.py` içinde `OrderCreate` sınıfının altına ekle:

```python
class OrderStatusUpdate(BaseModel):
    status: OrderStatus
```

- [ ] **Step 2: Failing test yaz**

`tests/test_order.py`:

```python
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
```

- [ ] **Step 3: Testi çalıştır, fail görmeli**

Run: `pytest tests/test_order.py -v`
Expected: FAIL — route yok (404).

- [ ] **Step 4: order.py endpoint'lerini yaz**

`app/api/endpoints/order.py`:

```python
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_admin
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
def all_orders(db: Session = Depends(get_db), current_admin: User = Depends(require_admin)):
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
    if order.user_id != current_user.id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Bu siparişe erişim yetkiniz yok.")
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Sipariş durumunu günceller. Sadece Adminler."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı.")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order
```

- [ ] **Step 5: order router'ını main.py'ye ekle**

`app/main.py` — import satırını güncelle:

```python
from app.api.endpoints import auth, category, product, cart, order
```

Router register bloğuna ekle (cart satırının altına):

```python
app.include_router(order.router, prefix="/orders", tags=["Siparişler"])
```

- [ ] **Step 6: Testi çalıştır, geçmeli**

Run: `pytest tests/test_order.py -v`
Expected: PASS (9 passed)

- [ ] **Step 7: Commit**

```bash
git add app/schemas/order.py app/api/endpoints/order.py app/main.py tests/test_order.py
git commit -m "feat: siparis endpoint'leri (olustur/listele/detay/admin/durum)"
```

---

## Task 5: PayTR yardımcı modülü

**Files:**
- Modify: `app/utils/paytr.py` (boş dosya doldurulur)
- Test: `tests/test_paytr.py`

**Interfaces:**
- Produces:
  - `generate_iframe_token(*, merchant_oid: str, email: str, amount: Decimal, user_ip: str, user_name: str, user_address: str, user_phone: str, items: list[dict]) -> str` (items: `[{"name": str, "unit_price": Decimal, "quantity": int}]`)
  - `verify_callback_hash(post_data: dict) -> bool`

- [ ] **Step 1: Failing test yaz**

`tests/test_paytr.py`:

```python
import base64
import hashlib
import hmac
from decimal import Decimal

from app.core.config import settings
from app.utils import paytr


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_generate_iframe_token_basarili(monkeypatch):
    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResp({"status": "success", "token": "iframe-token-123"})

    monkeypatch.setattr(paytr.requests, "post", fake_post)

    token = paytr.generate_iframe_token(
        merchant_oid="abc123",
        email="a@b.com",
        amount=Decimal("150.00"),
        user_ip="1.2.3.4",
        user_name="Ali",
        user_address="Adres",
        user_phone="555",
        items=[{"name": "Ürün", "unit_price": Decimal("75.00"), "quantity": 2}],
    )
    assert token == "iframe-token-123"
    # tutar kuruşa çevrilmeli
    assert captured["data"]["payment_amount"] == 15000
    assert captured["data"]["merchant_oid"] == "abc123"


def test_generate_iframe_token_hata_firlatir(monkeypatch):
    def fake_post(url, data=None, timeout=None):
        return _FakeResp({"status": "failed", "reason": "test hatası"})

    monkeypatch.setattr(paytr.requests, "post", fake_post)

    try:
        paytr.generate_iframe_token(
            merchant_oid="abc",
            email="a@b.com",
            amount=Decimal("10.00"),
            user_ip="1.2.3.4",
            user_name="Ali",
            user_address="Adres",
            user_phone="555",
            items=[{"name": "Ü", "unit_price": Decimal("10.00"), "quantity": 1}],
        )
        assert False, "hata bekleniyordu"
    except RuntimeError as e:
        assert "test hatası" in str(e)


def test_verify_callback_hash_dogru():
    merchant_oid = "order123"
    status = "success"
    total_amount = "15000"
    correct = base64.b64encode(
        hmac.new(
            settings.PAYTR_MERCHANT_KEY.encode(),
            (merchant_oid + settings.PAYTR_MERCHANT_SALT + status + total_amount).encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    post_data = {
        "merchant_oid": merchant_oid,
        "status": status,
        "total_amount": total_amount,
        "hash": correct,
    }
    assert paytr.verify_callback_hash(post_data) is True


def test_verify_callback_hash_yanlis():
    post_data = {
        "merchant_oid": "order123",
        "status": "success",
        "total_amount": "15000",
        "hash": "kesinlikle-yanlis-hash",
    }
    assert paytr.verify_callback_hash(post_data) is False
```

- [ ] **Step 2: Testi çalıştır, fail görmeli**

Run: `pytest tests/test_paytr.py -v`
Expected: FAIL — `paytr.generate_iframe_token` yok / `AttributeError`.

- [ ] **Step 3: paytr.py'yi yaz**

`app/utils/paytr.py`:

```python
import base64
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Dict, List

import requests

from app.core.config import settings

PAYTR_TOKEN_URL = "https://www.paytr.com/odeme/api/get-token"


def _to_kurus(amount: Decimal) -> int:
    """TL cinsinden Decimal tutarı kuruş (integer) yapar."""
    return int((amount * 100).to_integral_value())


def _build_basket(items: List[Dict]) -> str:
    """PayTR user_basket: base64(JSON [[ad, birim_fiyat_TL, adet], ...])."""
    basket = [[it["name"], f'{Decimal(it["unit_price"]):.2f}', it["quantity"]] for it in items]
    return base64.b64encode(json.dumps(basket).encode("utf-8")).decode("utf-8")


def generate_iframe_token(
    *,
    merchant_oid: str,
    email: str,
    amount: Decimal,
    user_ip: str,
    user_name: str,
    user_address: str,
    user_phone: str,
    items: List[Dict],
) -> str:
    """PayTR iFrame API'den ödeme token'ı üretir."""
    payment_amount = _to_kurus(amount)
    user_basket = _build_basket(items)
    no_installment = "0"
    max_installment = "0"
    currency = "TL"
    test_mode = str(settings.PAYTR_TEST_MODE)

    hash_str = (
        settings.PAYTR_MERCHANT_ID
        + user_ip
        + merchant_oid
        + email
        + str(payment_amount)
        + user_basket
        + no_installment
        + max_installment
        + currency
        + test_mode
    )
    paytr_token = base64.b64encode(
        hmac.new(
            settings.PAYTR_MERCHANT_KEY.encode(),
            (hash_str + settings.PAYTR_MERCHANT_SALT).encode(),
            hashlib.sha256,
        ).digest()
    ).decode()

    payload = {
        "merchant_id": settings.PAYTR_MERCHANT_ID,
        "user_ip": user_ip,
        "merchant_oid": merchant_oid,
        "email": email,
        "payment_amount": payment_amount,
        "paytr_token": paytr_token,
        "user_basket": user_basket,
        "debug_on": 1,
        "no_installment": no_installment,
        "max_installment": max_installment,
        "user_name": user_name,
        "user_address": user_address,
        "user_phone": user_phone,
        "merchant_ok_url": settings.PAYTR_OK_URL,
        "merchant_fail_url": settings.PAYTR_FAIL_URL,
        "timeout_limit": 30,
        "currency": currency,
        "test_mode": test_mode,
    }

    resp = requests.post(PAYTR_TOKEN_URL, data=payload, timeout=20)
    result = resp.json()
    if result.get("status") != "success":
        raise RuntimeError(f"PayTR token alınamadı: {result.get('reason')}")
    return result["token"]


def verify_callback_hash(post_data: Dict) -> bool:
    """PayTR webhook'unun gerçekliğini HMAC-SHA256 ile doğrular."""
    merchant_oid = post_data.get("merchant_oid", "")
    status = post_data.get("status", "")
    total_amount = post_data.get("total_amount", "")
    received_hash = post_data.get("hash", "")

    computed = base64.b64encode(
        hmac.new(
            settings.PAYTR_MERCHANT_KEY.encode(),
            (merchant_oid + settings.PAYTR_MERCHANT_SALT + status + total_amount).encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    return hmac.compare_digest(computed, received_hash)
```

- [ ] **Step 4: Testi çalıştır, geçmeli**

Run: `pytest tests/test_paytr.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/utils/paytr.py tests/test_paytr.py
git commit -m "feat: PayTR token uretimi ve webhook hash dogrulama"
```

---

## Task 6: Ödeme endpoint'leri (başlatma + webhook)

**Files:**
- Create: `app/api/endpoints/payment.py`
- Modify: `app/main.py`
- Test: `tests/test_payment.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_db`, `paytr.generate_iframe_token`, `paytr.verify_callback_hash`, `PaymentStartResponse`, `Order`, `Payment`, `ProductVariant`
- Produces: router `payment.router` with `POST /payments/start/{order_id}`, `POST /payments/callback`

- [ ] **Step 1: Failing test yaz**

`tests/test_payment.py`:

```python
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
    fresh = db.query(ProductVariant).filter(ProductVariant.id == variant.id).first()
    assert fresh.stock_qty == 10
```

- [ ] **Step 2: Testi çalıştır, fail görmeli**

Run: `pytest tests/test_payment.py -v`
Expected: FAIL — `app.api.endpoints.payment` modülü yok (ImportError).

- [ ] **Step 3: payment.py endpoint'lerini yaz**

`app/api/endpoints/payment.py`:

```python
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
```

- [ ] **Step 4: payment router'ını main.py'ye ekle**

`app/main.py` — import satırını güncelle:

```python
from app.api.endpoints import auth, category, product, cart, order, payment
```

Router register bloğuna ekle (order satırının altına):

```python
app.include_router(payment.router, prefix="/payments", tags=["Ödeme"])
```

- [ ] **Step 5: Testi çalıştır, geçmeli**

Run: `pytest tests/test_payment.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Tüm test suite'ini çalıştır**

Run: `pytest tests/ -v`
Expected: PASS (tümü yeşil — pricing, variant, cart, order, paytr, payment).

- [ ] **Step 7: Commit**

```bash
git add app/api/endpoints/payment.py app/main.py tests/test_payment.py
git commit -m "feat: odeme baslatma ve PayTR webhook endpoint'leri"
```

---

## Self-Review Notları

- **Spec kapsamı:** Variant (Task 2), sepet (Task 3), sipariş + admin + durum (Task 4), PayTR util (Task 5), ödeme start + webhook (Task 6), testler (her task'ta) → tüm spec bölümleri karşılandı.
- **Route sırası:** `GET /orders/admin/all`, `GET /orders/{order_id}`'den ÖNCE tanımlı (aksi halde "admin" order_id sanılır).
- **Stok:** Sipariş oluştururken sadece kontrol; webhook `success`'te düşer (idempotent).
- **Test izolasyonu:** PayTR HTTP çağrısı testte mock; webhook hash'i testte gerçek settings değerleriyle hesaplanır → gerçek PayTR hesabı gerekmez.
- **Not:** Testler PostgreSQL test veritabanı ister (`TEST_DATABASE_URL`), UUID/JSONB/ARRAY tipleri SQLite'ta çalışmaz.
