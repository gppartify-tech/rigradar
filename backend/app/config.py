"""Application settings, loaded from environment variables (or a .env file).

Every setting has a sensible default for local development, so the app runs
with zero configuration. Override anything in production via env vars, e.g.
DATABASE_URL=postgresql+psycopg://user:pass@db:5432/rigradar
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    app_name: str = "Partify"
    environment: str = "development"
    secret_key: str = "dev-secret-change-me-in-production-please-32+chars"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    frontend_url: str = "http://localhost:5173"
    # Comma separated list of origins allowed to call the API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    currency: str = "JOD"

    # --- Infrastructure ---
    database_url: str = "postgresql+psycopg://rigradar:rigradar@localhost:5432/rigradar"
    redis_url: str = "redis://localhost:6379/0"

    # --- Uploads (marketplace photos, avatars) ---
    upload_dir: str = "uploads"
    max_upload_mb: int = 5
    max_images_per_listing: int = 6

    # --- Scraping ---
    scrape_interval_hours: float = 6.0
    # Pause between two page requests to the same store (be polite!).
    scrape_delay_seconds: float = 2.5
    scraper_user_agent: str = (
        "Mozilla/5.0 (compatible; PartifyBot/1.0; academic price-comparison project)"
    )
    scraper_headless: bool = True
    # Only needed when the Playwright browser is installed in a custom location.
    playwright_chromium_path: str | None = None
    # Optional outbound proxy for the scraper browser, e.g. http://proxy.local:3128
    scraper_proxy: str | None = None
    scraper_max_pages_per_category: int = 15
    scraper_page_timeout_ms: int = 45_000
    # An offer that has not been seen for this many hours is marked inactive.
    offer_stale_after_hours: int = 72

    # --- E-mail (price alerts). Leave SMTP_HOST empty to only log e-mails. ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Partify <alerts@partify.local>"
    smtp_starttls: bool = True
    smtp_ssl: bool = False

    # --- Chatbot ---
    # Without a key the assistant falls back to the built-in rule-based recommender.
    anthropic_api_key: str | None = None
    chat_model: str = "claude-opus-5-5"
    # Thinking depth: low | medium | high | xhigh | max. "low" keeps chat replies fast and cheap.
    chat_effort: str = "low"
    chat_max_tokens: int = 16000
    # Max number of model <-> tool round trips for one user message.
    chat_max_tool_rounds: int = 6
    # If a safety classifier declines a request, let the API retry it on a fallback model.
    chat_fallbacks: bool = True
    chat_rate_limit_per_10min: int = 30

    # --- Seeding ---
    admin_email: str | None = None
    admin_password: str | None = None
    admin_username: str = "admin"
    # Load the bundled real-data snapshot into an empty catalog on startup.
    seed_sample_data: bool = True
    # Demo accounts + marketplace ads for presentations. They share a public password: keep OFF in production.
    seed_demo_users: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
