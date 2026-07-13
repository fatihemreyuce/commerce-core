# Backend Sağlamlaştırma: RBAC + Auth + CORS + Favorites — Tasarım

**Tarih:** 2026-07-13
**Durum:** Onay bekliyor
**Kapsam:** Frontend geliştirmesine geçmeden önce backend'in ihtiyaç duyduğu API yüzeyini doğru ve güvenli tamamlamak.

## Amaç

Mevcut backend'de `role == admin` şeklinde ikili bir yetki kontrolü var; gerçek bir yetki (RBAC) sistemi yok. Ayrıca frontend'i doğrudan etkileyen/bloklayan eksikler mevcut: refresh token akışı yok, CORS yanlış yapılandırılmış, favoriler modeli ölü kod. Bu tasarım bu dört maddeyi kapsar.

**Kapsam DIŞI (ikinci tura ertelendi):** login rate-limit / brute-force, şifre güç politikası, merkezi logging + global exception handler, `updated_at` / soft-delete. Bunlar değerli ama frontend'i bloklamıyor.

---

## 1. RBAC (Kod-tabanlı Permission)

### Karar
Roller ve yetkiler **kodda sabit** tanımlanır. DB tablosu (roles/permissions/role_permissions) **eklenmez** — bu ölçekte (3 rol, nadir değişim) DB-tabanlı RBAC gereksiz karmaşıklık ve bug yüzeyi getirir. İleride runtime yönetim gerekirse DB'ye taşınabilir.

### Roller
`UserRole` enum'una üçüncü değer eklenir:
- `customer` (mevcut, varsayılan)
- `admin` (mevcut)
- `staff` (**yeni**) — mağaza operasyonu

### Permission seti
`app/core/permissions.py` içinde `Permission` enum'u:

| Permission | Açıklama |
|---|---|
| `product:manage` | Ürün + varyant oluştur/güncelle/sil |
| `category:manage` | Kategori oluştur/güncelle/sil |
| `order:read_all` | Tüm siparişleri görüntüle |
| `order:update_status` | Sipariş durumu değiştir |
| `user:manage` | Kullanıcı oluştur (rol atayarak) |

### Rol → permission haritası

| | product:manage | category:manage | order:read_all | order:update_status | user:manage |
|---|:---:|:---:|:---:|:---:|:---:|
| **admin** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **staff** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **customer** | ❌ | ❌ | ❌ | ❌ | ❌ |

`staff` = ürün/kategori/sipariş yönetir; **kullanıcı/rol yönetemez** (sadece admin).

### Bileşenler
- **`app/core/permissions.py`** (yeni): `Permission` enum, `ROLE_PERMISSIONS: dict[UserRole, set[Permission]]`, `has_permission(role, permission) -> bool` yardımcısı.
- **`app/core/deps.py`**: `require_permission(permission: Permission)` factory dependency eklenir. Kullanıcının rolü ilgili permission'a sahip değilse `403` döner (mevcut `require_admin`'in mesaj/kod davranışıyla tutarlı).
- **`require_admin` korunur** — geriye dönük uyumluluk. Anlamı artık `require_permission(Permission.USER_MANAGE)`'e denktir; mevcut kullanımları kademeli olarak `require_permission`'a taşınır.

### Endpoint güncellemeleri
Mevcut `Depends(require_admin)` kullanımları ilgili permission ile değiştirilir:

| Endpoint | Yeni koruma |
|---|---|
| `category` create/update/delete | `require_permission(CATEGORY_MANAGE)` |
| `product` create/update/delete/variant | `require_permission(PRODUCT_MANAGE)` |
| `order` admin listeleme | `require_permission(ORDER_READ_ALL)` |
| `order` durum güncelleme | `require_permission(ORDER_UPDATE_STATUS)` |
| `auth` admin/users (kullanıcı oluştur) | `require_permission(USER_MANAGE)` |

### Migration
`UserRole` enum'una `staff` değeri eklemek Postgres'te `ALTER TYPE ... ADD VALUE 'staff'` gerektirir → bir Alembic migration dosyası. (Not: `ADD VALUE` bir transaction bloğu içinde çalıştırılamaz; migration buna göre yazılır.)

### Test
- `has_permission` matrisi için birim testler (her rol × her permission).
- `require_permission` için: staff bir user:manage endpoint'ine erişince 403, product:manage'e erişince izin.
- Mevcut admin testleri geçmeye devam etmeli (regresyon).

---

## 2. Auth Tamamlama (Refresh + Logout)

### Token type claim (güvenlik düzeltmesi)
Şu an access ve refresh token'ları yapısal olarak aynı (`{exp, sub}`); biri diğerinin yerine kullanılabilir. Düzeltme:
- `create_access_token` → payload'a `"type": "access"` eklenir.
- `create_refresh_token` → payload'a `"type": "refresh"` eklenir.
- `get_current_user` yalnızca `type == "access"` kabul eder; aksi halde `401`.
- `/auth/refresh` yalnızca `type == "refresh"` kabul eder; aksi halde `401`.

### Login değişikliği
`/auth/login` yanıtı `access_token`'a ek olarak `refresh_token` da döner. `user` bloğu korunur.

### Yeni endpoint: `POST /auth/refresh`
- Girdi: `refresh_token` (body).
- Doğrular (imza, süre, `type == "refresh"`), `sub`'daki kullanıcıyı bulur, aktifse yeni `access_token` üretir ve döner.
- Geçersiz/süresi dolmuş/yanlış tipte token → `401`.

### Logout
**Stateless.** Backend logout endpoint'i **yok**; frontend token'ları siler. Refresh token ömrü kısa tutulur (mevcut 7 gün ayarı korunur). Token iptali gerektiren senaryo çıkarsa ikinci turda DB denylist eklenir.

### Test
- Refresh mutlu yol: geçerli refresh token → yeni access token.
- Access token ile `/auth/refresh` denemesi → 401.
- Refresh token ile korumalı bir endpoint denemesi → 401.
- Login yanıtında refresh_token bulunması.

---

## 3. CORS Düzeltmesi

### Sorun
`main.py`'de `allow_origins=["*"]` + `allow_credentials=True` — tarayıcılar bu kombinasyonu reddeder ve güvensizdir.

### Çözüm
- `app/core/config.py`'ye `BACKEND_CORS_ORIGINS` ayarı eklenir (env'den okunur, virgülle ayrılmış origin listesi olarak parse edilir). Dev varsayılanı: `http://localhost:3000` (frontend için).
- `main.py`'de `allow_origins` bu listeye bağlanır. `allow_credentials=True` artık geçerli.

### Test
- Manuel/otomatik: izinli origin'den preflight geçer, izinsiz origin'e CORS header dönmez. (Birim test opsiyonel; en azından ayarın parse edilmesi test edilir.)

---

## 4. Favorites Endpoint

`Favorite` modeli zaten mevcut (`user_id`, `product_id`, `created_at`, `(user_id, product_id)` unique). Endpoint yok — canlıya alınır.

### Bileşenler
- **`app/schemas/favorite.py`** (yeni): `FavoriteCreate` (`product_id`), `FavoriteResponse` (favori + ürün özeti).
- **`app/api/endpoints/favorite.py`** (yeni): `/favorites` router'ı, hepsi `get_current_user` ile korumalı.
- **`main.py`**: router `/favorites` prefix'iyle kaydedilir.

### Endpoint'ler
- `POST /favorites` — `product_id` ile favoriye ekler. Ürün yoksa `404`. Zaten favorideyse (unique çakışması) `400`.
- `DELETE /favorites/{product_id}` — kendi favorisinden çıkarır. Yoksa `404`.
- `GET /favorites` — kullanıcının favorilerini ürün detaylarıyla listeler.

### Test
- Ekle → listele → çıkar mutlu yolu.
- Aynı ürünü iki kez ekleme → 400.
- Başka kullanıcının favorisini silme denemesi çıkışsız kalır (ownership; kendi kaydı olmadığından 404).
- Auth'suz istek → 401.

---

## Genel Notlar
- Tüm yeni kod mevcut desen ve Türkçe yorum/mesaj üslubunu takip eder.
- Her madde ayrı, atomik commit'ler halinde uygulanır.
- Migration'lar Alembic ile; mevcut test session yapısı korunur.
