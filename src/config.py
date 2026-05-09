"""
config.py — Environment variable configuration
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Claude / Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Freshdesk
    freshdesk_domain: str = ""          # e.g. "yourcompany.freshdesk.com"
    freshdesk_api_key: str = ""         # Freshdesk API key (Profile Settings)

    # PostgreSQL
    database_url: str = "postgresql://triage:triage@localhost:5432/triage"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Optional: webhook secret for Freshdesk signature verification
    freshdesk_webhook_secret: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
