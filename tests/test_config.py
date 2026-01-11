"""Tests for the config module."""

import os
import pytest
from review_roadmap.config import Settings


class TestGetGithubTokens:
    """Tests for Settings.get_github_tokens method."""
    
    def test_get_github_tokens_single_token(self, monkeypatch):
        """Returns single GITHUB_TOKEN when no multi-token configured."""
        # Clear any env vars that might interfere
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            GITHUB_TOKEN="single-token",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None  # Disable .env file loading
        )
        
        tokens = settings.get_github_tokens()
        
        assert tokens == ["single-token"]
    
    def test_get_github_tokens_multi_token_precedence(self, monkeypatch):
        """REVIEW_ROADMAP_GITHUB_TOKENS takes precedence over GITHUB_TOKEN."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            GITHUB_TOKEN="fallback-token",
            REVIEW_ROADMAP_GITHUB_TOKENS="token1,token2,token3",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None
        )
        
        tokens = settings.get_github_tokens()
        
        # Multi-tokens should come first, fallback token appended
        assert tokens == ["token1", "token2", "token3", "fallback-token"]
    
    def test_get_github_tokens_strips_whitespace(self, monkeypatch):
        """Whitespace is stripped from comma-separated tokens."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            REVIEW_ROADMAP_GITHUB_TOKENS=" token1 , token2 , token3 ",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None
        )
        
        tokens = settings.get_github_tokens()
        
        assert tokens == ["token1", "token2", "token3"]
    
    def test_get_github_tokens_no_duplicates(self, monkeypatch):
        """GITHUB_TOKEN is not duplicated if already in REVIEW_ROADMAP_GITHUB_TOKENS."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            GITHUB_TOKEN="token1",
            REVIEW_ROADMAP_GITHUB_TOKENS="token1,token2",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None
        )
        
        tokens = settings.get_github_tokens()
        
        # token1 should not be duplicated
        assert tokens == ["token1", "token2"]
    
    def test_get_github_tokens_skips_empty(self, monkeypatch):
        """Empty tokens from extra commas are skipped."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            REVIEW_ROADMAP_GITHUB_TOKENS="token1,,token2,",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None
        )
        
        tokens = settings.get_github_tokens()
        
        assert tokens == ["token1", "token2"]


class TestGetDefaultGithubToken:
    """Tests for Settings.get_default_github_token method."""
    
    def test_get_default_github_token_returns_first(self, monkeypatch):
        """Returns the first token from the tokens list."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            REVIEW_ROADMAP_GITHUB_TOKENS="first-token,second-token",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None
        )
        
        token = settings.get_default_github_token()
        
        assert token == "first-token"
    
    def test_get_default_github_token_uses_github_token_fallback(self, monkeypatch):
        """Falls back to GITHUB_TOKEN when no multi-token configured."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        settings = Settings(
            GITHUB_TOKEN="my-github-token",
            REVIEW_ROADMAP_MODEL_NAME="test-model",
            _env_file=None
        )
        
        token = settings.get_default_github_token()
        
        assert token == "my-github-token"


class TestSettingsValidation:
    """Tests for Settings validation."""
    
    def test_requires_at_least_one_token(self, monkeypatch):
        """Raises error when no GitHub tokens are configured."""
        # Must clear env vars so pydantic-settings doesn't pick them up
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("REVIEW_ROADMAP_GITHUB_TOKENS", raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            Settings(
                REVIEW_ROADMAP_MODEL_NAME="test-model",
                _env_file=None
                # No GITHUB_TOKEN or REVIEW_ROADMAP_GITHUB_TOKENS
            )
        
        # Should mention needing a token
        assert "GITHUB_TOKEN" in str(exc_info.value) or "REVIEW_ROADMAP_GITHUB_TOKENS" in str(exc_info.value)
