"""Analyzer app configuration."""
from django.apps import AppConfig


class AnalyzerConfig(AppConfig):
    """Configuration for the analyzer application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analyzer'
    verbose_name = 'Codebase Analyzer'
