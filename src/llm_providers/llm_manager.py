"""
LLM Provider Manager.
Orchestrates primary/secondary LLM switching on rate-limits, timeouts, or API failures.
"""

import logging
from typing import List, Dict, Any, Tuple
from src.llm_providers.base import BaseLLMProvider
from src.llm_providers.claude_provider import ClaudeProvider
from src.llm_providers.openai_provider import OpenAIProvider
from src.config import config

logger = logging.getLogger(__name__)


class LLMFallbackManager:
    """Manages fallback execution across Anthropic Claude and OpenAI GPT providers."""

    def __init__(self):
        self.providers: List[BaseLLMProvider] = []

        # Attempt to initialize Primary Provider (Claude)
        try:
            self.providers.append(ClaudeProvider())
            logger.info("Initialized Primary LLM Provider: Claude")
        except Exception as e:
            logger.warning(f"Could not initialize Primary LLM Provider (Claude): {e}")

        # Attempt to initialize Fallback Provider (OpenAI) if enabled
        if config.enable_llm_fallback:
            try:
                self.providers.append(OpenAIProvider())
                logger.info("Initialized Fallback LLM Provider: OpenAI")
            except Exception as e:
                logger.warning(f"Could not initialize Fallback LLM Provider (OpenAI): {e}")

        if not self.providers:
            raise RuntimeError("No LLM Providers could be initialized. Please check your API keys in .env.")

    async def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]], Any, str]:
        """
        Attempts tool calling generation across providers sequentially.
        Returns: (text_content, tool_calls, raw_response, active_provider_name)
        """
        last_exception = None

        for provider in self.providers:
            try:
                logger.info(f"Attempting tool call with LLM Provider: {provider.provider_name}")
                text, tool_calls, raw_resp = await provider.generate_tool_call(
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt
                )
                return text, tool_calls, raw_resp, provider.provider_name

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