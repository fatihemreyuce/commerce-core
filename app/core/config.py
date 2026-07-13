from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    PAYTR_MERCHANT_ID: str
    PAYTR_MERCHANT_KEY: str
    PAYTR_MERCHANT_SALT: str
    PAYTR_TEST_MODE: int = 1
    PAYTR_CALLBACK_URL: str
    PAYTR_OK_URL: str = "https://yourdomain.com/payment/success"
    PAYTR_FAIL_URL: str = "https://yourdomain.com/payment/fail"

    UPLOAD_DIR: str = "./uploads"

    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    # .env dosyasından okuması için gerekli ayar
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

# Proje genelinde ayarları 'settings' objesi üzerinden çağıracağız
settings = Settings()