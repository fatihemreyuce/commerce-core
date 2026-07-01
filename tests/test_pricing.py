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


def test_root_endpoint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()
