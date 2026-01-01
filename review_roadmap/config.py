"""Application configuration using pydantic-settings.

This module provides centralized configuration management, loading settings
from environment variables and .env files. All settings use the REVIEW_ROADMAP_
prefix to avoid conflicts with shell environment variables.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file.

    Settings are loaded in order of precedence:
    1. Environment variables (highest priority)
    2. .env file in current directory
    3. Default values defined here (lowest priority)

    Attributes:
        GITHUB_TOKEN: GitHub API token for fetching PR data.
        REVIEW_ROADMAP_LLM_PROVIDER: LLM provider to use. Options:
            'anthropic', 'anthropic-vertex', 'openai', 'google'.
        REVIEW_ROADMAP_MODEL_NAME: Model name (e.g., 'claude-opus-4-5', 'gpt-4o').
        ANTHROPIC_API_KEY: API key for direct Anthropic API access.
        OPENAI_API_KEY: API key for OpenAI.
        GOOGLE_API_KEY: API key for Google AI (Gemini).
        ANTHROPIC_VERTEX_PROJECT_ID: GCP project ID for Anthropic via Vertex AI.
        ANTHROPIC_VERTEX_REGION: GCP region for Vertex AI (default: 'us-east5').
        GOOGLE_APPLICATION_CREDENTIALS: Path to GCP service account credentials.
        REVIEW_ROADMAP_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR).
        REVIEW_ROADMAP_LOG_FORMAT: Log output format ('console' or 'json').
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # GitHub
    GITHUB_TOKEN: str

    # LLM Configuration (prefixed to avoid conflicts with shell environment)
    REVIEW_ROADMAP_LLM_PROVIDER: str = "anthropic"
    REVIEW_ROADMAP_MODEL_NAME: str

    # API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # Anthropic Vertex AI Configuration (alternative to ANTHROPIC_API_KEY)
    ANTHROPIC_VERTEX_PROJECT_ID: Optional[str] = None
    ANTHROPIC_VERTEX_REGION: str = "us-east5"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None

    # App Config (prefixed to avoid conflicts with shell environment)
    REVIEW_ROADMAP_LOG_LEVEL: str = "INFO"
    REVIEW_ROADMAP_LOG_FORMAT: str = "console"

    def get_google_credentials_path(self) -> Optional[str]:
        """Find the Google Application Credentials file path.

        Checks for credentials in the following order:
        1. Explicit GOOGLE_APPLICATION_CREDENTIALS environment variable
        2. Default gcloud location: ~/.config/gcloud/application_default_credentials.json
        3. Windows location: %APPDATA%/gcloud/application_default_credentials.json

        Returns:
            Path to the credentials file if found, None otherwise.
        """
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
