# Sepet → Sipariş → Ödeme Akışı — Tasarım Dokümanı

**Tarih:** 2026-07-01
**Kapsam:** E-ticaret backend'ine sepet, sipariş ve PayTR ödeme akışının eklenmesi.

## 1. Amaç

Proje şu an auth + katalog (ürün/kategori) seviyesinde çalışıyor. Sepet, sipariş ve
ödeme modelleri veritabanında mevcut ama endpoint'leri yok. `app/utils/paytr.py` boş.
Bu iş, kullanıcının ürün seçmesinden ödeme onayına kadar olan tam akışı tamamlar.

Ek zorunluluk: `cart_items` ve `order_items` bir `product_variant`'a bağlı, ama şu an
sisteme variant ekleyecek endpoint yok. Bu yüzden variant oluşturma endpoint'i de bu
kapsama dahildir.

## 2. Genel Akış

```
Variant oluştur (admin)
        ↓
Sepete ekle  →  GET /cart, POST /cart/items ...
        ↓
Sipariş oluştur  →  POST /orders  (sepetten, stok KONTROL edilir, düşmez, Order=pending)
        ↓
Ödeme başlat  →  POST /payments/start/{order_id}  (PayTR iframe token)
        ↓
Kullanıcı iframe'de öder
        ↓
PayTR webhook  →  POST /payments/callback  (hash doğrula → Payment=paid, Order=paid, STOK DÜŞER)
```

## 3. Fiyatlama Kuralı (her katmanda tutarlı)

Bir variant'ın efektif fiyatı:

```
unit_price = variant.price_override  (dolu ise)
           = product.base_price       (aksi halde)
```

Bu fiyat **snapshot** olarak yazılır:
- Sepete eklerken → `cart_item.unit_price`
- Sipariş oluştururken → `order_item.unit_price`

Böylece ürün fiyatı sonradan değişse bile mevcut sepet/sipariş fiyatı sabit kalır.

## 4. Stok Yönetimi

- **Sipariş oluştururken (`POST /orders`):** her satır için `variant.stock_qty >= quantity`
  kontrol edilir. Yetersizse `400` döner. Stok **düşürülmez**.
- **Ödeme onaylanınca (webhook `status=success`):** her `order_item` için
  `variant.stock_qty -= quantity` uygulanır. Bu işlem tek bir DB transaction'ında yapılır.

Böylece ödemeyen kullanıcılar stok kilitlemez (overselling riski kabul edilir; ileride
rezervasyon modeline geçilebilir).

## 5. Endpoint'ler

### 5.1 Variant (product.py'ye eklenir)
| Method | Path | Yetki | Açıklama |
|--------|------|-------|----------|
| POST | `/products/{product_id}/variants` | admin | Ürüne variant ekle (renk/beden/SKU/stok/görsel) |
| DELETE | `/products/variants/{variant_id}` | admin | Variant sil |

- Variant oluştururken `product_id` var mı kontrol edilir (404).
- `sku` benzersizliği kontrol edilir (400).
- Şema: mevcut `ProductVariantCreate` / `ProductVariantResponse` kullanılır.

### 5.2 Sepet (app/api/endpoints/cart.py) — `get_current_user`
| Method | Path | Açıklama |
|--------|------|----------|
| GET | `/cart` | Kullanıcının sepetini getir; yoksa oluştur |
| POST | `/cart/items` | `{variant_id, quantity}` ekle; aynı variant varsa adet artar |
| PUT | `/cart/items/{item_id}` | Adet güncelle (0 veya altı → 400) |
| DELETE | `/cart/items/{item_id}` | Satırı sil |
| DELETE | `/cart` | Sepeti boşalt |

- Her kullanıcının tek sepeti vardır (`carts.user_id` unique).
- Item eklerken variant var mı kontrol edilir (404).
- `unit_price` fiyatlama kuralına göre yazılır.
- Item işlemlerinde sahiplik kontrolü: item, isteği yapan kullanıcının sepetine ait olmalı.

### 5.3 Sipariş (app/api/endpoints/order.py)
| Method | Path | Yetki | Açıklama |
|--------|------|-------|----------|
| POST | `/orders` | user | `{shipping_address}` — sepetten sipariş üret |
| GET | `/orders` | user | Kendi siparişlerim |
| GET | `/orders/{id}` | user | Sipariş detayı (sahiplik kontrolü, 404/403) |
| GET | `/orders/admin/all` | admin | Tüm siparişler |
| PATCH | `/orders/{id}/status` | admin | Durum güncelle (OrderStatus enum) |

`POST /orders` akışı:
1. Kullanıcının sepetini bul; boşsa `400`.
2. Her cart_item için variant'ı çek, `stock_qty >= quantity` kontrol et (yetersizse `400`,
   hangi ürün olduğu mesajda).
3. `total_amount = Σ (unit_price × quantity)`.
4. `Order(status=pending, total_amount, shipping_address)` + her satır için `OrderItem`
   (fiyat snapshot) oluştur.
5. Sepeti temizle (cart_items sil).
6. Order'ı döndür.

Tüm adım tek transaction; hata olursa rollback.

### 5.4 Ödeme (app/api/endpoints/payment.py)
| Method | Path | Yetki | Açıklama |
|--------|------|-------|----------|
| POST | `/payments/start/{order_id}` | user | PayTR iframe token üret, Payment kaydı aç |
| POST | `/payments/callback` | herkese açık* | PayTR webhook |

`POST /payments/start/{order_id}`:
1. Order kullanıcıya ait mi + status `pending` mi kontrol et.
2. Zaten bir Payment varsa onu kullan/güncelle (idempotent), yoksa oluştur.
3. `paytr.generate_iframe_token(...)` çağır → token.
4. `Payment.paytr_token` kaydet, `{iframe_token}` döndür (`PaymentStartResponse`).

`POST /payments/callback` (*herkese açık ama hash ile doğrulanır):
1. Form POST verisini al (`merchant_oid`, `status`, `total_amount`, `hash`).
2. `paytr.verify_callback_hash(...)` — geçersizse `PAYTR notification failed` (ama yine de
   PayTR'ye anlamlı yanıt). Geçersiz hash'te işlem yapılmaz.
3. `merchant_oid`'den ilgili Order/Payment bulunur.
4. `status == "success"`: Payment `paytr_status=success`, `paid_at=now`, `raw_webhook` kaydet;
   Order `paid`; her order_item için stok düş. (Idempotent: zaten paid ise tekrar düşme.)
5. `status == "failed"`: Payment `paytr_status=failed`, `raw_webhook` kaydet.
6. Her durumda PayTR'ye düz metin **`OK`** döndür (yoksa PayTR tekrar dener).

## 6. PayTR Modülü (app/utils/paytr.py)

`merchant_oid` olarak Order UUID'sinin tire'siz hali kullanılır (PayTR alfanumerik ister).

```python
def generate_iframe_token(*, order, user, items, user_ip, user_name, user_address, user_phone) -> str
def verify_callback_hash(post_data: dict) -> bool
```

- **Token üretimi:** `user_basket` = base64(JSON [[ad, birim_fiyat, adet], ...]).
  `hash_str = merchant_id + user_ip + merchant_oid + email + payment_amount + user_basket +
  no_installment + max_installment + currency + test_mode`.
  `paytr_token = base64( HMAC-SHA256( hash_str + merchant_salt, merchant_key ) )`.
  `https://www.paytr.com/odeme/api/get-token`'a POST; yanıt `status=success` ise `token` döner,
  değilse `reason` ile hata fırlatılır.
- **Callback doğrulama:** `hash = base64( HMAC-SHA256( merchant_oid + merchant_salt + status +
  total_amount, merchant_key ) )`; gelen `hash` ile karşılaştır.
- Tutarlar **kuruş** cinsinden (TL × 100, integer).
- `test_mode` = `settings.PAYTR_TEST_MODE`.

## 7. Şema Değişiklikleri

- `app/schemas/order.py` → `OrderStatusUpdate { status: OrderStatus }` eklenir.
- Diğer şemalar mevcut (cart, payment, product variant) — yeniden kullanılır.

## 8. Diğer Değişiklikler

- `requirements.txt` → `requests` (PayTR HTTP), `pytest`, `httpx` (test) eklenir.
- `app/main.py` → `cart`, `order`, `payment` router'ları register edilir.
- Router prefix'leri: `/cart`, `/orders`, `/payments`.

## 9. Testler (pytest)

`tests/` altında:
- Sepete ekleme + fiyat snapshot doğruluğu.
- Sipariş oluşturma: başarılı akış + yetersiz stok → 400 + boş sepet → 400.
- Ödeme başlatma: `requests.post` **mock**'lanır (gerçek PayTR'ye gidilmez), token döner.
- Webhook: geçerli hash + success → Order paid + stok düşer; geçersiz hash → işlem yok.

### Test altyapısı notları
- **Postgres-özel tipler** (UUID, JSONB, ARRAY) SQLite ile çalışmaz → testler bir test
  PostgreSQL veritabanı kullanır. Plan aşamasında: ayrı test DB URL'i + fixture ile
  şema kurulumu (create_all) ve her testte temizlik.
- PayTR HTTP çağrısı ve callback hash üretimi testte mock/gerçek-hesap ile izole edilir.

## 10. Kapsam Dışı (YAGNI)

- Refresh token endpoint'i (ayrı iş).
- Kupon/indirim, kargo ücreti hesaplama.
- Kısmi ödeme / iade akışı.
- Stok rezervasyon modeli (şimdilik webhook'ta düşüm yeterli).
