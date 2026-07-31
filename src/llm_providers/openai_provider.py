"""
OpenAI LLM Provider (Fallback).
Model Agnostic so can switch models through .env
"""

import json
import logging
from typing import List, Dict, Any, Tuple
from openai import AsyncOpenAI
from src.llm_providers.base import BaseLLMProvider
from src.config import config

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation."""

    def __init__(self):
        if not config.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment.")
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self.model = config.openai_model_id

    @property
    def provider_name(self) -> str:
        return f"OpenAI ({self.model})"

    def _convert_tools_to_openai_format(self, anthropic_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert standard tool definitions to OpenAI's function format."""
        openai_tools = []
        for tool in anthropic_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {})
                }
            })
        return openai_tools

    async def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]], Any]:
        logger.info(f"[{self.provider_name}] Generating completion with tool definitions...")

        # Format messages including system prompt for OpenAI
        formatted_messages = [{"role": "system", "content": system_prompt}] + messages
        openai_tools = self._convert_tools_to_openai_format(tools)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            tools=openai_tools,
            tool_choice="auto",
            max_tokens=2048,
            timeout=config.llm_timeout_seconds
        )

        choice = response.choices[0].message
        text_content = choice.content or ""
        tool_calls = []

        if choice.tool_calls:
            for tc in choice.tool_calls:
                args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args
                })

        return text_content, tool_calls, response

    async def generate_final_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str
    ) -> str:
        logger.info(f"[{self.provider_name}] Generating final recommendation text...")

        formatted_messages = [{"role": "system", "content": system_prompt}] + messages

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            max_tokens=2048,
            timeout=config.llm_timeout_seconds
        )

        return response.choices[0].message.content or ""