from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str
    DATABASE_SYNC_URL: str
    DEBUG: bool = True

    APP_NAME: str = "Tekken Tournament Management System"
    APP_VERSION: str = "1.0.0"

    ALLOWED_ORIGINS: list = ["*"]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()