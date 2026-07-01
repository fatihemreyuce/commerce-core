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
    # test_mode PayTR'nin beklediği "1"/"0" string'i olmalı
    assert captured["data"]["test_mode"] in ("1", "0")


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
