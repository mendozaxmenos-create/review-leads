from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_places_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, validation_alias=AliasChoices("PORT", "APP_PORT"))
    debug: bool = False

    database_path: str = "data/review-leads.db"
    cache_ttl_hours: int = 24
    nominatim_contact_email: str = ""

    outreach_sender_name: str = "Gustavo"
    outreach_sender_company: str = "SofIA"


def outreach_sender_signature() -> str:
    name = settings.outreach_sender_name.strip()
    company = settings.outreach_sender_company.strip()
    if name and company:
        return f"{name} de {company}"
    return name or company or "nuestro estudio"


settings = Settings()
