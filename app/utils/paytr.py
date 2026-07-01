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
    test_mode = "1" if settings.PAYTR_TEST_MODE else "0"

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
