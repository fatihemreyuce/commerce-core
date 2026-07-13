# Backend Sağlamlaştırma (RBAC + Auth + CORS + Favorites) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend'e geçmeden önce backend'e gerçek bir RBAC sistemi, refresh token akışı, doğru CORS yapılandırması ve favoriler endpoint'lerini eklemek.

**Architecture:** Kod-tabanlı permission sistemi (`Permission` enum + `ROLE_PERMISSIONS` haritası + `require_permission` factory dependency). Yeni `staff` rolü. Access/refresh token'lara `type` claim'i. CORS origin listesi env'den. Favoriler için mevcut model üzerine schema + endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, python-jose (JWT HS256), pytest.

## Global Constraints

- Türkçe yorum ve hata mesajı üslubu korunur (mevcut kod stiliyle tutarlı).
- Her task atomik commit ile biter; TDD (önce başarısız test).
- Testler mevcut `tests/conftest.py` altyapısını kullanır (Postgres test DB, `Base.metadata.create_all`, fixture'lar).
- Postgres enum tip adı: `userrole` (SQLAlchemy `Enum(UserRole)` varsayılanı).
- Yeni DB tablosu EKLENMEZ (RBAC kod-tabanlı). Sadece `staff` enum değeri eklenir.
- Migration'lar `alembic/versions/` altına, mevcut `9a8946bfb50e_init.py` desenini takip eder.

---

### Task 1: Permission modeli ve `has_permission`

**Files:**
- Create: `app/core/permissions.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- Produces:
  - `class Permission(str, Enum)` — değerler: `PRODUCT_MANAGE="product:manage"`, `CATEGORY_MANAGE="category:manage"`, `ORDER_READ_ALL="order:read_all"`, `ORDER_UPDATE_STATUS="order:update_status"`, `USER_MANAGE="user:manage"`
  - `ROLE_PERMISSIONS: dict[UserRole, set[Permission]]`
  - `has_permission(role: UserRole, permission: Permission) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_permissions.py
from app.models.user import UserRole
from app.core.permissions import Permission, has_permission


def test_admin_has_all_permissions():
    for perm in Permission:
        assert has_permission(UserRole.admin, perm) is True


def test_staff_manages_catalog_and_orders_but_not_users():
    assert has_permission(UserRole.staff, Permission.PRODUCT_MANAGE) is True
    assert has_permission(UserRole.staff, Permission.CATEGORY_MANAGE) is True
    assert has_permission(UserRole.staff, Permission.ORDER_READ_ALL) is True
    assert has_permission(UserRole.staff, Permission.ORDER_UPDATE_STATUS) is True
    assert has_permission(UserRole.staff, Permission.USER_MANAGE) is False


def test_customer_has_no_admin_permissions():
    for perm in Permission:
        assert has_permission(UserRole.customer, perm) is False
```

Not: `UserRole.staff` Task 2'de eklenecek. Bu test o ana kadar `AttributeError` ile başarısız olur — beklenen davranış (Step 2).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_permissions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.permissions'` (ve/veya `staff` yok).

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/permissions.py
import enum
from app.models.user import UserRole


class Permission(str, enum.Enum):
    """Sistemdeki tüm yetkiler (kaynak:aksiyon)."""
    PRODUCT_MANAGE = "product:manage"
    CATEGORY_MANAGE = "category:manage"
    ORDER_READ_ALL = "order:read_all"
    ORDER_UPDATE_STATUS = "order:update_status"
    USER_MANAGE = "user:manage"


# Her rolün sahip olduğu yetkiler. Admin her şeyi yapar; staff kullanıcı yönetemez.
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.admin: set(Permission),
    UserRole.staff: {
        Permission.PRODUCT_MANAGE,
        Permission.CATEGORY_MANAGE,
        Permission.ORDER_READ_ALL,
        Permission.ORDER_UPDATE_STATUS,
    },
    UserRole.customer: set(),
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    """Verilen rolün belirtilen yetkiye sahip olup olmadığını döner."""
    return permission in ROLE_PERMISSIONS.get(role, set())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_permissions.py -v`
Expected: PASS (Task 2 tamamlandıktan sonra; sıralı ilerleniyorsa Task 2'yi önce bitirin veya bu testi Task 2 sonrası çalıştırın).

> Sıralama notu: Task 1 ve Task 2 birbirine bağlı (`staff`). İkisini de tamamlayıp testi Task 2 sonunda yeşile alın. Commit'ler ayrı kalır.

- [ ] **Step 5: Commit**

```bash
git add app/core/permissions.py tests/test_permissions.py
git commit -m "feat: kod-tabanli permission modeli (Permission enum + has_permission)"
```

---

### Task 2: `staff` rolü + Alembic migration

**Files:**
- Modify: `app/models/user.py:11-13` (UserRole enum)
- Create: `alembic/versions/<yeni>_add_staff_role.py`

**Interfaces:**
- Produces: `UserRole.staff = "staff"` (enum değeri)

- [ ] **Step 1: Add staff to the enum**

`app/models/user.py` içinde `UserRole` sınıfını güncelle:

```python
class UserRole(str, enum.Enum):
    customer = "customer"
    admin = "admin"
    staff = "staff"
```

- [ ] **Step 2: Verify Task 1 tests now pass**

Run: `pytest tests/test_permissions.py -v`
Expected: PASS (3 test).

- [ ] **Step 3: Create the Alembic migration**

Yeni dosya `alembic/versions/b1staffrole01_add_staff_role.py`:

```python
"""add staff role to userrole enum

Revision ID: b1staffrole01
Revises: 9a8946bfb50e
Create Date: 2026-07-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b1staffrole01"
down_revision: Union[str, Sequence[str], None] = "9a8946bfb50e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE transaction bloğu içinde çalışamaz;
    # autocommit_block ile ayrı çalıştırıyoruz.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'staff'")


def downgrade() -> None:
    # Postgres enum değeri silmeyi desteklemez; downgrade no-op.
    pass
```

> Not: `down_revision`'ın mevcut son migration ID'si (`9a8946bfb50e`) olduğunu doğrulayın: `alembic heads`. Farklıysa gerçek head ID'sini yazın.

- [ ] **Step 4: Apply migration to a real DB (opsiyonel doğrulama)**

Run: `alembic upgrade head`
Expected: Hatasız tamamlanır. (Test DB'si `create_all` kullandığından testler migration'a bağlı değildir.)

- [ ] **Step 5: Commit**

```bash
git add app/models/user.py alembic/versions/b1staffrole01_add_staff_role.py
git commit -m "feat: staff rolu ekle (enum + alembic migration)"
```

---

### Task 3: `require_permission` dependency + staff test fixture'ları

**Files:**
- Modify: `app/core/deps.py` (yeni `require_permission` factory ekle)
- Modify: `tests/conftest.py` (staff fixture'ları ekle)
- Test: `tests/test_rbac.py`

**Interfaces:**
- Consumes: `Permission`, `has_permission` (Task 1)
- Produces: `require_permission(permission: Permission) -> Callable` — FastAPI dependency döndürür; yetkisizse `403`, yetkiliyse `User` döner.

- [ ] **Step 1: Add staff fixtures to conftest**

`tests/conftest.py` sonuna ekle (mevcut `admin_headers` desenini takip eder):

```python
@pytest.fixture
def staff_user(db):
    user = User(
        email="staff@test.com",
        full_name="Staff",
        hashed_password=get_password_hash("secret123"),
        role=UserRole.staff,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def staff_headers(staff_user):
    token = create_access_token(subject=str(staff_user.id))
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_rbac.py
def test_staff_can_create_category(client, staff_headers):
    resp = client.post("/categories/", json={"name": "Elektronik", "slug": "elektronik"}, headers=staff_headers)
    assert resp.status_code == 201


def test_staff_cannot_create_user(client, staff_headers):
    resp = client.post(
        "/auth/admin/users",
        json={"email": "x@x.com", "password": "secret123", "full_name": "X", "role": "customer"},
        headers=staff_headers,
    )
    assert resp.status_code == 403


def test_customer_cannot_create_category(client, user_headers):
    resp = client.post("/categories/", json={"name": "Giyim", "slug": "giyim"}, headers=user_headers)
    assert resp.status_code == 403


def test_admin_can_create_user(client, admin_headers):
    resp = client.post(
        "/auth/admin/users",
        json={"email": "new@x.com", "password": "secret123", "full_name": "New", "role": "staff"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
```

> Bu testler Task 4 (endpoint göçü) tamamlanınca tam yeşile döner. Step 3'te dependency'yi, Task 4'te endpoint bağlamalarını yaparız.

- [ ] **Step 3: Implement require_permission in deps.py**

`app/core/deps.py` içine, mevcut `require_admin`'in altına ekle. Üstteki import bloğuna `from app.core.permissions import Permission, has_permission` ekle:

```python
def require_permission(permission: Permission):
    """Belirtilen yetkiye sahip kullanıcıları geçiren dependency üretir."""

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yeterli yetkiniz bulunmuyor.",
            )
        return current_user

    return _checker
```

- [ ] **Step 4: Run RBAC tests (kısmi)**

Run: `pytest tests/test_rbac.py -v`
Expected: Endpoint'ler henüz göç etmediği için bazıları FAIL olabilir (staff hâlâ `require_admin` ile 403 alır). Tam PASS Task 4 sonunda. Bu adımda en az `test_admin_can_create_user` ve `test_customer_cannot_create_category` geçmeli.

- [ ] **Step 5: Commit**

```bash
git add app/core/deps.py tests/conftest.py tests/test_rbac.py
git commit -m "feat: require_permission dependency + staff test fixture'lari"
```

---

### Task 4: Endpoint'leri `require_permission`'a taşı

**Files:**
- Modify: `app/api/endpoints/category.py:16,49,68`
- Modify: `app/api/endpoints/product.py:5,21,53,74,96`
- Modify: `app/api/endpoints/order.py:7,78,93,103`
- Modify: `app/api/endpoints/auth.py:4,61`

**Interfaces:**
- Consumes: `require_permission`, `Permission` (Task 3)

- [ ] **Step 1: Migrate category.py**

`category.py` üst importuna ekle: `from app.core.permissions import Permission`. `from app.core.deps import get_db, require_admin` → `from app.core.deps import get_db, require_permission`. Üç endpoint'te (create/update/delete) `current_admin: User = Depends(require_admin)` → `_user: User = Depends(require_permission(Permission.CATEGORY_MANAGE))`.

- [ ] **Step 2: Migrate product.py**

`product.py:5` importunu güncelle: `from app.core.deps import get_db, require_permission` ve `from app.core.permissions import Permission` ekle. Dört yerde (`create_product:21`, `delete_product:53`, `create_variant:74`, `delete_variant:96`) `Depends(require_admin)` → `Depends(require_permission(Permission.PRODUCT_MANAGE))`.

- [ ] **Step 3: Migrate order.py**

`order.py:7` importunu güncelle: `from app.core.deps import get_db, get_current_user, require_permission` ve `from app.core.permissions import Permission, has_permission` ekle.
- `all_orders:78`: `Depends(require_admin)` → `Depends(require_permission(Permission.ORDER_READ_ALL))`.
- `update_order_status:103`: `Depends(require_admin)` → `Depends(require_permission(Permission.ORDER_UPDATE_STATUS))`.
- `order_detail:93` erişim kontrolünü permission tutarlı yap:

```python
    if order.user_id != current_user.id and not has_permission(
        current_user.role, Permission.ORDER_READ_ALL
    ):
        raise HTTPException(status_code=403, detail="Bu siparişe erişim yetkiniz yok.")
```

`UserRole` importu order.py'de başka yerde kullanılmıyorsa kalabilir; kullanılmıyorsa dokunmayın (regresyon riskini azaltmak için import satırını olduğu gibi bırakmak yeterli).

- [ ] **Step 4: Migrate auth.py**

`auth.py:4` importunu güncelle: `from app.core.deps import get_db, require_permission` ve `from app.core.permissions import Permission` ekle. `admin_create_user:61`: `_admin: User = Depends(require_admin)` → `_admin: User = Depends(require_permission(Permission.USER_MANAGE))`.

- [ ] **Step 5: Run full RBAC + regression tests**

Run: `pytest tests/test_rbac.py tests/test_admin_users.py -v`
Expected: PASS (staff artık kategori/ürün oluşturabilir; kullanıcı oluşturamaz; mevcut admin testleri geçer).

- [ ] **Step 6: Run whole suite**

Run: `pytest -q`
Expected: Tüm testler PASS (regresyon yok).

- [ ] **Step 7: Commit**

```bash
git add app/api/endpoints/category.py app/api/endpoints/product.py app/api/endpoints/order.py app/api/endpoints/auth.py
git commit -m "refactor: endpoint yetkilerini require_permission'a tasi"
```

---

### Task 5: Token `type` claim + `get_current_user` doğrulaması

**Files:**
- Modify: `app/core/security.py` (`create_access_token`, `create_refresh_token`)
- Modify: `app/core/deps.py` (`get_current_user` type kontrolü)
- Test: `tests/test_auth_tokens.py`

**Interfaces:**
- Produces: access token payload `{"exp", "sub", "type": "access"}`; refresh token payload `{"exp", "sub", "type": "refresh"}`. `get_current_user` sadece `type == "access"` kabul eder.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth_tokens.py
from app.core.security import create_access_token, create_refresh_token
from jose import jwt
from app.core.config import settings
from app.core.security import ALGORITHM


def test_access_token_has_type_claim(normal_user):
    token = create_access_token(subject=str(normal_user.id))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["type"] == "access"


def test_refresh_token_has_type_claim(normal_user):
    token = create_refresh_token(subject=str(normal_user.id))
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["type"] == "refresh"


def test_refresh_token_rejected_on_protected_endpoint(client, normal_user):
    refresh = create_refresh_token(subject=str(normal_user.id))
    resp = client.get("/orders/", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_tokens.py -v`
Expected: FAIL — `KeyError: 'type'` ve refresh token korumalı endpoint'te 200 (henüz reddedilmiyor).

- [ ] **Step 3: Add type claims in security.py**

`create_access_token` içindeki `to_encode`:

```python
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
```

`create_refresh_token` içindeki `to_encode`:

```python
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
```

- [ ] **Step 4: Enforce type in get_current_user**

`app/core/deps.py` `get_current_user` içinde, `payload` çözüldükten sonra `user_id` kontrolünden önce ekle:

```python
        if payload.get("type") != "access":
            raise credentials_exception
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_auth_tokens.py -v`
Expected: PASS (3 test).

- [ ] **Step 6: Regression**

Run: `pytest -q`
Expected: Tüm testler PASS (conftest `create_access_token` kullandığından mevcut auth'lu testler etkilenmez).

- [ ] **Step 7: Commit**

```bash
git add app/core/security.py app/core/deps.py tests/test_auth_tokens.py
git commit -m "feat: access/refresh token type claim + get_current_user dogrulamasi"
```

---

### Task 6: `/auth/refresh` endpoint + login refresh token

**Files:**
- Modify: `app/api/endpoints/auth.py` (login yanıtı + refresh endpoint)
- Modify: `app/schemas/user.py` (`RefreshRequest` şeması)
- Test: `tests/test_auth_refresh.py`

**Interfaces:**
- Consumes: `create_refresh_token`, `create_access_token`, `get_current_user` type doğrulaması (Task 5)
- Produces: `POST /auth/refresh` (body: `{"refresh_token": str}`) → `{"access_token", "token_type"}`; login yanıtına `refresh_token` eklenir.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_auth_refresh.py
def test_login_returns_refresh_token(client, normal_user):
    resp = client.post("/auth/login", json={"email": "user@test.com", "password": "secret123"})
    assert resp.status_code == 200
    assert "refresh_token" in resp.json()


def test_refresh_returns_new_access_token(client, normal_user):
    from app.core.security import create_refresh_token
    refresh = create_refresh_token(subject=str(normal_user.id))
    resp = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_refresh_rejects_access_token(client, normal_user):
    from app.core.security import create_access_token
    access = create_access_token(subject=str(normal_user.id))
    resp = client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_refresh.py -v`
Expected: FAIL — login'de `refresh_token` yok; `/auth/refresh` route yok (404/405).

- [ ] **Step 3: Add RefreshRequest schema**

`app/schemas/user.py` sonuna:

```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

- [ ] **Step 4: Update login to return refresh token**

`app/api/endpoints/auth.py` import satırına `create_refresh_token` ve `from jose import jwt, JWTError`, `from app.core.config import settings`, `from app.core.security import ALGORITHM`, `from app.schemas.user import ... , RefreshRequest` ekle. `login` fonksiyonunda access token üretiminin altına ekle ve dönüş sözlüğüne `refresh_token` koy:

```python
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
        },
    }
```

- [ ] **Step 5: Add /auth/refresh endpoint**

`auth.py` içine yeni endpoint (register/login ile aynı router):

```python
@router.post("/refresh")
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Geçerli bir refresh token karşılığında yeni access token üretir."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş yenileme token'ı.",
    )
    try:
        data = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if data.get("type") != "refresh":
            raise credentials_exception
        user_id = data.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise credentials_exception

    new_access = create_access_token(subject=str(user.id))
    return {"access_token": new_access, "token_type": "bearer"}
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_auth_refresh.py -v`
Expected: PASS (3 test).

- [ ] **Step 7: Regression**

Run: `pytest -q`
Expected: Tüm testler PASS.

- [ ] **Step 8: Commit**

```bash
git add app/api/endpoints/auth.py app/schemas/user.py tests/test_auth_refresh.py
git commit -m "feat: /auth/refresh endpoint + login refresh token donusu"
```

---

### Task 7: CORS yapılandırması (env'den origin listesi)

**Files:**
- Modify: `app/core/config.py` (`BACKEND_CORS_ORIGINS` ayarı)
- Modify: `app/main.py` (CORS middleware)
- Test: `tests/test_cors.py`

**Interfaces:**
- Produces: `settings.cors_origins_list -> list[str]` (virgülle ayrılmış string'i listeye çevirir).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cors.py
def test_cors_allows_configured_origin(client):
    resp = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cors.py -v`
Expected: FAIL — mevcut `allow_origins=["*"]` + `allow_credentials=True` ile echo edilen origin `"*"` değil; ya da header yıldız döner → eşitlik başarısız.

- [ ] **Step 3: Add setting to config.py**

`app/core/config.py` `Settings` sınıfına ekle (UPLOAD_DIR yakınına):

```python
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
```

ve sınıf içine yardımcı property:

```python
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]
```

- [ ] **Step 4: Update main.py CORS middleware**

`app/main.py` içinde `from app.core.config import settings` importunu ekle (yoksa) ve middleware'i güncelle:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 5: Run test**

Run: `pytest tests/test_cors.py -v`
Expected: PASS.

- [ ] **Step 6: Regression**

Run: `pytest -q`
Expected: Tüm testler PASS.

- [ ] **Step 7: Commit**

```bash
git add app/core/config.py app/main.py tests/test_cors.py
git commit -m "fix: CORS origin listesini env'den oku (wildcard+credentials duzeltmesi)"
```

---

### Task 8: Favorites endpoint (schema + endpoint + router)

**Files:**
- Modify: `app/models/favorite.py` (product relationship ekle)
- Create: `app/schemas/favorite.py`
- Create: `app/api/endpoints/favorite.py`
- Modify: `app/main.py` (router kaydı)
- Test: `tests/test_favorites.py`

**Interfaces:**
- Consumes: `get_current_user`, `Favorite` modeli, `ProductResponse` (mevcut)
- Produces: `POST /favorites`, `DELETE /favorites/{product_id}`, `GET /favorites`.

- [ ] **Step 1: Add product relationship to Favorite model**

`app/models/favorite.py`'ye `relationship` importu ve `product` ilişkisi ekle:

```python
from sqlalchemy.orm import relationship
```

`Favorite` sınıfının `__table_args__`'ından önce:

```python
    product = relationship("Product")
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_favorites.py
def test_add_list_remove_favorite(client, user_headers, make_variant):
    variant = make_variant()
    product_id = str(variant.product_id)

    add = client.post("/favorites", json={"product_id": product_id}, headers=user_headers)
    assert add.status_code == 201

    listing = client.get("/favorites", headers=user_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["product"]["id"] == product_id

    remove = client.delete(f"/favorites/{product_id}", headers=user_headers)
    assert remove.status_code == 204

    empty = client.get("/favorites", headers=user_headers)
    assert empty.json() == []


def test_duplicate_favorite_returns_400(client, user_headers, make_variant):
    variant = make_variant()
    pid = str(variant.product_id)
    client.post("/favorites", json={"product_id": pid}, headers=user_headers)
    dup = client.post("/favorites", json={"product_id": pid}, headers=user_headers)
    assert dup.status_code == 400


def test_favorites_requires_auth(client):
    resp = client.get("/favorites")
    assert resp.status_code in (401, 403)


def test_remove_nonexistent_favorite_returns_404(client, user_headers, make_variant):
    variant = make_variant()
    resp = client.delete(f"/favorites/{variant.product_id}", headers=user_headers)
    assert resp.status_code == 404
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_favorites.py -v`
Expected: FAIL — `/favorites` route yok (404).

- [ ] **Step 4: Create favorite schema**

```python
# app/schemas/favorite.py
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.product import ProductResponse


class FavoriteCreate(BaseModel):
    product_id: uuid.UUID


class FavoriteResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    product: ProductResponse

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 5: Create favorite endpoint**

```python
# app/api/endpoints/favorite.py
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
```

> Not: Testte `POST /favorites` (sondaki slash olmadan) çağrılıyor; FastAPI varsayılan olarak `/favorites` → `/favorites/` yönlendirmesi yapar. Tutarlılık için testler ve router prefix'i uyumlu; 307 redirect TestClient tarafından takip edilir.

- [ ] **Step 6: Register router in main.py**

`app/main.py` import satırına `favorite` ekle:

```python
from app.api.endpoints import auth, category, product, cart, order, payment, favorite
```

Router kayıtlarının sonuna ekle:

```python
app.include_router(favorite.router, prefix="/favorites", tags=["Favoriler"])
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_favorites.py -v`
Expected: PASS (4 test).

- [ ] **Step 8: Full regression**

Run: `pytest -q`
Expected: Tüm testler PASS.

- [ ] **Step 9: Commit**

```bash
git add app/models/favorite.py app/schemas/favorite.py app/api/endpoints/favorite.py app/main.py tests/test_favorites.py
git commit -m "feat: favoriler endpoint'leri (ekle/listele/cikar)"
```

---

## Notlar
- Task 1 ve Task 2 `staff` enum değeri üzerinden bağlı; ikisini ardışık tamamlayın.
- Task 3'ün RBAC testleri Task 4 sonunda tam yeşile döner (endpoint göçü sonrası).
- Postgres enum tip adının `userrole` olduğunu migration öncesi doğrulayın; farklıysa migration'daki adı düzeltin.
- `.env`'e canlıda `BACKEND_CORS_ORIGINS=https://frontend-domain.com` eklenecek (deployment notu).
