"""Tests for the logging configuration module."""

import logging
from unittest.mock import patch, MagicMock

import pytest
import structlog


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_console_format(self):
        """Test configuring logging with console format."""
        from review_roadmap.logging import configure_logging

        # Should not raise
        configure_logging(log_level="INFO", log_format="console")

        # Verify root logger is configured
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_configure_logging_json_format(self):
        """Test configuring logging with JSON format."""
        from review_roadmap.logging import configure_logging

        # Should not raise
        configure_logging(log_level="DEBUG", log_format="json")

        # Verify root logger is configured with DEBUG level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_configure_logging_sets_log_level(self):
        """Test that different log levels are properly set."""
        from review_roadmap.logging import configure_logging

        test_cases = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]

        for level_name, expected_level in test_cases:
            configure_logging(log_level=level_name, log_format="console")
            root_logger = logging.getLogger()
            assert root_logger.level == expected_level, f"Failed for {level_name}"

    def test_configure_logging_quiets_noisy_loggers(self):
        """Test that httpx and httpcore loggers are set to WARNING."""
        from review_roadmap.logging import configure_logging

        configure_logging(log_level="DEBUG", log_format="console")

        # Even with DEBUG, these should be WARNING
        httpx_logger = logging.getLogger("httpx")
        httpcore_logger = logging.getLogger("httpcore")

        assert httpx_logger.level == logging.WARNING
        assert httpcore_logger.level == logging.WARNING

    def test_configure_logging_invalid_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        from review_roadmap.logging import configure_logging

        configure_logging(log_level="INVALID_LEVEL", log_format="console")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_bound_logger(self):
        """Test that get_logger returns a structlog BoundLogger."""
        from review_roadmap.logging import configure_logging, get_logger

        # Configure first
        configure_logging(log_level="INFO", log_format="console")

        logger = get_logger("test_module")

        # Should be a structlog logger
        assert logger is not None
        # Should have standard logging methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_with_different_names(self):
        """Test getting loggers with different names."""
        from review_roadmap.logging import configure_logging, get_logger

        configure_logging(log_level="INFO", log_format="console")

        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        # Both should be valid loggers
        assert logger1 is not None
        assert logger2 is not None

    def test_logger_can_log_messages(self, capsys):
        """Test that the logger can actually log messages."""
        from review_roadmap.logging import configure_logging, get_logger

        configure_logging(log_level="INFO", log_format="console")
        logger = get_logger("test_logging")

        # This should not raise
        logger.info("test_message", key="value")

        # Note: Output goes to stderr, and structlog formatting may vary
        # The main point is that it doesn't raise an exception

