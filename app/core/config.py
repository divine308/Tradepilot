from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trade Pilot AI"
    environment: str = "development"

    secret_key: str
    access_token_expire_minutes: int = 10080

    database_url: str = "sqlite+aiosqlite:///./tradepilot.db"

    frontend_url: str = "http://localhost:5173"

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_paper: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()