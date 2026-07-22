from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    ENVIRONMENT: str = "development"
    DATABASE_URL: str

    CORS_ORIGINS: str = "http://localhost:3000"

    # Background scheduler (route-call status transitions). Tests set it to False
    # so pytest never starts a scheduler that writes to the shared database.
    SCHEDULER_ENABLED: bool = True

    CLERK_SECRET_KEY: str | None = None
    CLERK_WEBHOOK_SECRET: str | None = None
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS as a list (comma-separated in the .env)."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()