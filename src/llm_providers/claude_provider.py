"""
Claude LLM Provider Implementation.
Model Agnostic so can switch models through .env
"""

import logging
from typing import List, Dict, Any, Tuple
from anthropic import AsyncAnthropic
from src.llm_providers.base import BaseLLMProvider
from src.config import config

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude provider implementation."""

    def __init__(self):
        if not config.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set in environment.")
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
        self.model = config.anthropic_model_id

    @property
    def provider_name(self) -> str:
        return f"Anthropic Claude ({self.model})"

    async def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int], Any]:
        logger.info(f"[{self.provider_name}] Generating completion with tool definitions...")

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            tools=tools,
            timeout=config.llm_timeout_seconds
        )

        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input
                })

        # Token metrics dict
        token_usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }

        return text_content, tool_calls, token_usage, response

    async def generate_final_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str
    ) -> str:
        logger.info(f"[{self.provider_name}] Generating final recommendation text...")

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            timeout=config.llm_timeout_seconds
        )

        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content += block.text

        return text_content