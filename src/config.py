"""
Configuration module for Mercari AI Shopper.
Centralizes environment variable loading, default thresholds, and feature flags.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application Settings mapped from .env file. Make sure var names here match the ones in .env for auto-mapping."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Feature Flags
    enable_llm_fallback: bool = True
    enable_mercari_fallback: bool = True
    enable_mercari_fallback_mercarpi: bool = True
    enable_mercari_fallback_playwright: bool = True
    enable_followup_questions: bool = True

    # Operational Parameters
    max_tool_call_loops: int = 5
    request_timeout_seconds: float = 15.0
    max_items_per_search: int = 10
    max_description_length: int = 1500

    # Default LLM Models
    # !TODO: Add these options in .env and declare them as provider-specific models instead of Primary or Fallback, this should be handled by the provider interface
    anthropic_model_id: str = "claude-3-5-sonnet-20240620"
    openai_model_id: str = "gpt-4o"


# Global configuration instance
config = AppConfig()