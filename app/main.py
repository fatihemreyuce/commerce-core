from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Router'ımızı içeri aktarıyoruz
from app.api.endpoints import auth

app = FastAPI(title="E-Ticaret API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Canlıda buraya Frontend domaini yazılır
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Kimlik Doğrulama"])

@app.get("/")
def root():
    return {"message": "E-Ticaret API'sine Hoş Geldiniz!"}