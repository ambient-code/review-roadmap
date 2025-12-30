from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # GitHub
    GITHUB_TOKEN: str

    # LLM Configuration (prefixed to avoid conflicts with shell environment)
    REVIEW_ROADMAP_LLM_PROVIDER: str = "anthropic"  # 'anthropic', 'openai', or 'google'
    REVIEW_ROADMAP_MODEL_NAME: str  # Must be set in .env (e.g. claude-3-5-sonnet-xxxx, gpt-4o)

    # API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # App Config (prefixed to avoid conflicts with shell environment)
    REVIEW_ROADMAP_LOG_LEVEL: str = "INFO"

settings = Settings()
