import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # GitHub
    GITHUB_TOKEN: str

    # LLM Configuration (prefixed to avoid conflicts with shell environment)
    REVIEW_ROADMAP_LLM_PROVIDER: str = "anthropic"  # 'anthropic', 'anthropic-vertex', 'openai', or 'google'
    REVIEW_ROADMAP_MODEL_NAME: str  # Must be set in .env (e.g. claude-3-5-sonnet-xxxx, gpt-4o)

    # API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # Anthropic Vertex AI Configuration (alternative to ANTHROPIC_API_KEY)
    ANTHROPIC_VERTEX_PROJECT_ID: Optional[str] = None
    ANTHROPIC_VERTEX_REGION: str = "us-east5"  # Default region for Claude on Vertex
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # App Config (prefixed to avoid conflicts with shell environment)
    REVIEW_ROADMAP_LOG_LEVEL: str = "INFO"
    REVIEW_ROADMAP_LOG_FORMAT: str = "console"  # 'console' for pretty output, 'json' for structured

    def get_google_credentials_path(self) -> Optional[str]:
        """Get the Google Application Credentials path, checking env var and default locations."""
        # First check explicit env var
        if self.GOOGLE_APPLICATION_CREDENTIALS:
            return self.GOOGLE_APPLICATION_CREDENTIALS
        
        # Check default gcloud locations
        default_paths = [
            Path.home() / ".config" / "gcloud" / "application_default_credentials.json",
            Path(os.environ.get("APPDATA", "")) / "gcloud" / "application_default_credentials.json",
        ]
        
        for path in default_paths:
            if path.exists():
                return str(path)
        
        return None

settings = Settings()
