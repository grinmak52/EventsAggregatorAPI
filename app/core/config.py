from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Events Aggregator"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/events"
    provider_url: str = "https://events-provider.dev-2.python-labs.ru"
    provider_api_key: str = ""
    sync_interval_seconds: int = 24 * 60 * 60

    postgres_host: str | None = None
    postgres_port: int = 5432
    postgres_username: str = ""
    postgres_password: str = ""
    postgres_database_name: str = ""

    @model_validator(mode="after")
    def build_database_url(self):
        if self.postgres_host:
            user = quote_plus(self.postgres_username)
            password = quote_plus(self.postgres_password)
            host = self.postgres_host
            port = self.postgres_port
            name = self.postgres_database_name
            self.database_url = (
                f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
            )
        return self


settings = Settings()
