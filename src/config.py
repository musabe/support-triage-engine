"""
config.py — Environment variable configuration
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Claude / Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5"

    # Freshdesk
    freshdesk_domain: str = ""          # e.g. "yourcompany.freshdesk.com"
    freshdesk_api_key: str = ""         # Freshdesk API key (Profile Settings)

    # Jira Cloud
    jira_domain: str = ""              # e.g. "yourcompany.atlassian.net"
    jira_email: str = ""               # your Jira account email
    jira_api_token: str = ""           # API token from id.atlassian.com/manage-profile/security
    jira_issue_types: str = "Bug,Support"  # comma-separated issue types to triage

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
