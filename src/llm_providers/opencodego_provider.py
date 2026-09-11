"""OpenCode Go provider using its OpenAI-compatible chat-completions API."""

import json
import logging
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from openai import AsyncOpenAI

from src.config import config
from src.llm_providers.base import BaseLLMProvider, normalize_openai_messages

logger = logging.getLogger(__name__)


class OpenCodeGoProvider(BaseLLMProvider):
    """Send shopping-agent tool calls through OpenCode Go chat completions."""

    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        if not config.opencodego_api_key:
            raise ValueError("OPENCODEGO_API_KEY is not set in the environment.")

        self.model = config.opencodego_model_id
        self.session_id = str(uuid4())
        self.client = client or AsyncOpenAI(
            api_key=config.opencodego_api_key,
            base_url=config.opencodego_base_url.rstrip("/") + "/",
            default_headers={
                "User-Agent": "mercari-shopper-ai-agent/1.0",
                "x-opencode-session": self.session_id,
            },
        )
        logger.info("[OPENCODEGO_PROVIDER_INITIALIZED] model=%s", self.model)

    @property
    def provider_name(self) -> str:
        """Return the selected OpenCode Go model without exposing session data."""
        return f"OpenCode Go ({self.model})"

    @staticmethod
    def _convert_tools_to_openai_format(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert the harness tool schema into OpenAI-compatible function tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
            for tool in tools
        ]

    async def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str,
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int], Any]:
        """Generate text or function calls with the configured compatible model."""
        logger.info("[OPENCODEGO_REQUEST] model=%s", self.model)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=normalize_openai_messages(messages, system_prompt),
            tools=self._convert_tools_to_openai_format(tools),
            tool_choice=(
                {"type": "function", "function": {"name": "final_recommendation"}}
                if len(tools) == 1 and tools[0]["name"] == "final_recommendation"
                else "auto"
            ),
            max_tokens=2048,
            timeout=config.llm_timeout_seconds,
        )
        choice = response.choices[0].message
        tool_calls = []
        for tool_call in choice.tool_calls or []:
            arguments = tool_call.function.arguments
            tool_calls.append(
                {
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": json.loads(arguments) if isinstance(arguments, str) else arguments,
                }
            )

        usage = response.usage
        return choice.content or "", tool_calls, {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
        }, response

    async def generate_final_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
    ) -> str:
        """Generate a final recommendation without passing tool definitions."""
        logger.info("[OPENCODEGO_REQUEST] model=%s", self.model)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=normalize_openai_messages(messages, system_prompt),
            max_tokens=2048,
            timeout=config.llm_timeout_seconds,
        )
        return response.choices[0].message.content or ""
