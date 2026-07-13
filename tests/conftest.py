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
