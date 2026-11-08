"""Tests for the logging module."""

import logging

from utils.log import log


class TestLog:
    """Tests for utils.log module."""

    def test_logger_exists(self):
        """Logger is instantiated and accessible."""
        assert log is not None
        assert isinstance(log, logging.Logger)

    def test_logger_level(self):
        """Logger level is set to DEBUG."""
        assert log.level == logging.DEBUG

    def test_logger_has_handler(self):
        """Logger has at least one handler (StreamHandler)."""
        assert len(log.handlers) >= 1
        handler = log.handlers[0]
        assert isinstance(handler, logging.StreamHandler)

    def test_logger_format(self):
        """Logger formatter uses the expected color format."""
        formatter = log.handlers[0].formatter
        assert hasattr(formatter, "log_colors")
        assert "DEBUG" in formatter.log_colors
        assert "INFO" in formatter.log_colors
        assert "WARNING" in formatter.log_colors
        assert "ERROR" in formatter.log_colors
        assert "CRITICAL" in formatter.log_colors
