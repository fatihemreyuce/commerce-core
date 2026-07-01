from decimal import Decimal


def effective_unit_price(variant) -> Decimal:
    """Variant'ın efektif birim fiyatı: override doluysa o, değilse ürünün base_price'ı."""
    if variant.price_override is not None:
        return variant.price_override
    return variant.product.base_price
