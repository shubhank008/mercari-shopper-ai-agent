"""
LLM Provider Manager.
Orchestrates primary/secondary LLM switching on rate-limits, timeouts, or API failures.
"""

import logging
from typing import List, Dict, Any, Tuple
from src.llm_providers.base import BaseLLMProvider
from src.llm_providers.claude_provider import ClaudeProvider
from src.llm_providers.openai_provider import OpenAIProvider
from src.llm_providers.opencodego_provider import OpenCodeGoProvider
from src.config import config

logger = logging.getLogger(__name__)


class LLMFallbackManager:
    """Manages a configured primary provider and optional deterministic fallbacks."""

    _provider_factories = {
        "anthropic": ClaudeProvider,
        "openai": OpenAIProvider,
        "opencodego": OpenCodeGoProvider,
    }
    _fallback_order = ("anthropic", "openai", "opencodego")

    def __init__(self) -> None:
        self.providers: List[BaseLLMProvider] = []
        provider_names = [config.llm_primary_provider]
        if config.enable_llm_fallback:
            provider_names.extend(
                name for name in self._fallback_order if name != config.llm_primary_provider
            )

        for name in provider_names:
            self._initialize_provider(name, primary=name == config.llm_primary_provider)

        if not self.providers:
            raise RuntimeError("No LLM providers could be initialized. Check the selected provider credentials.")

    def _initialize_provider(self, name: str, primary: bool) -> None:
        """Initialize one configured provider without preventing later fallbacks."""
        try:
            provider = self._provider_factories[name]()
            self.providers.append(provider)
            role = "primary" if primary else "fallback"
            logger.info("Initialized %s LLM provider: %s", role, provider.provider_name)
        except Exception as exc:
            role = "primary" if primary else "fallback"
            logger.warning("Could not initialize %s LLM provider %s: %s", role, name, exc)

    async def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int], Any, str]:
        """
        Attempts tool calling generation across providers sequentially.
        Returns: (text_content, tool_calls, token_usage, raw_response, active_provider_name)
        """
        last_exception = None

        for provider in self.providers:
            try:
                logger.info(f"Attempting tool call with LLM Provider: {provider.provider_name}")
                text, tool_calls, usage, raw_resp = await provider.generate_tool_call(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt
                )
                return text, tool_calls, usage, raw_resp, provider.provider_name

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM Provider '{provider.provider_name}' failed: {e}. "
                    f"Trying fallback provider..."
                )

        raise RuntimeError(f"All LLM Providers failed to generate tool call. Last error: {last_exception}")

    async def generate_final_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str
    ) -> Tuple[str, str]:
        """
        Attempts final response generation across providers sequentially.
        Returns: (response_text, active_provider_name)
        """
        last_exception = None

        for provider in self.providers:
            try:
                logger.info(f"Generating final response with LLM Provider: {provider.provider_name}")
                text = await provider.generate_final_response(
                    messages=messages,
                    system_prompt=system_prompt
                )
                return text, provider.provider_name

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM Provider '{provider.provider_name}' failed: {e}. "
                    f"Trying fallback provider..."
                )

        raise RuntimeError(f"All LLM Providers failed to generate final response. Last error: {last_exception}")