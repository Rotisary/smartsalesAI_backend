from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"

    # JWT Auth
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Google Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # WhatsApp Cloud API (Meta)
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_API_VERSION: str = "v19.0"
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    WHATSAPP_TOKEN_ENCRYPTION_KEY: str = ""

    # Business defaults
    DEFAULT_AI_PERSONA_NAME: str = "Aria"
    DEFAULT_BUSINESS_NAME: str = "Acme Store"

    # Knowledge document
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024
    PRESIGNED_URL_TTL: int = 300

    # embedding
    EMBEDDING_MODEL: str = "models/text-embedding-004"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
