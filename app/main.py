from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# Tüm router'ları tek bir satırda, tek seferde import ediyoruz
from app.api.endpoints import auth, category, product, cart, order, payment

app = FastAPI(title="E-Ticaret API", version="1.0.0")

# Frontend'in API'ye istek atabilmesi için CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları uygulamaya tek seferde dahil ediyoruz
app.include_router(auth.router, prefix="/auth", tags=["Kimlik Doğrulama"])
app.include_router(category.router, prefix="/categories", tags=["Kategoriler"])
app.include_router(product.router, prefix="/products", tags=["Ürünler"])
app.include_router(cart.router, prefix="/cart", tags=["Sepet"])
app.include_router(order.router, prefix="/orders", tags=["Siparişler"])
app.include_router(payment.router, prefix="/payments", tags=["Ödeme"])

@app.get("/")
def root():
    return {"message": "E-Ticaret API'sine Hoş Geldiniz!"}