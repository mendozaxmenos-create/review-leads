from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_places_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    database_path: str = "data/review-leads.db"
    cache_ttl_hours: int = 24


settings = Settings()
