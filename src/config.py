from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # GitHub
    GITHUB_TOKEN: str

    # LLM Providers (Optional to allow fallback/selection)
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # App Config
    LOG_LEVEL: str = "INFO"

settings = Settings()
