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

    # Twilio WhatsApp Business (plantillas Meta)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""  # ej. whatsapp:+14155238886 o whatsapp:+549...
    twilio_template_sid: str = ""  # Content SID de la plantilla aprobada
    twilio_send_enabled: bool = False  # false = dry-run (no llama a Twilio)
    twilio_send_delay_seconds: float = 3.0  # sandbox: 1 msg / 3s; prod puede bajar a ~1–2s


def outreach_sender_signature() -> str:
    name = settings.outreach_sender_name.strip()
    company = settings.outreach_sender_company.strip()
    if name and company:
        return f"{name} de {company}"
    return name or company or "nuestro estudio"


settings = Settings()
