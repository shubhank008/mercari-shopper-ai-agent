"""
Base LLM Provider Interface.
Defines standard abstract interface for Anthropic, OpenAI, and any future LLM backends (openrouter / openweight).
"""

import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple



def normalize_openai_messages(
    messages: List[Dict[str, Any]],
    system_prompt: str,
) -> List[Dict[str, Any]]:
    """Convert Anthropic-style harness turns into OpenAI-compatible messages."""
    normalized: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            normalized.append(message)
            continue

        role = message["role"]
        if role == "assistant":
            text_parts = [block["text"] for block in content if block.get("type") == "text"]
            tool_calls = [
                {
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                    },
                }
                for block in content
                if block.get("type") == "tool_use"
            ]
            normalized.append({
                "role": "assistant",
                "content": "\n".join(text_parts) or None,
                **({"tool_calls": tool_calls} if tool_calls else {}),
            })
        elif role == "user":
            for block in content:
                if block.get("type") == "tool_result":
                    normalized.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block.get("content", ""),
                    })
                else:
                    normalized.append({"role": "user", "content": block.get("text", "")})
        else:
            normalized.append({"role": role, "content": content})
    return normalized


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns provider identification string."""
        pass

    @abstractmethod
    async def generate_tool_call(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int], Any]:
        """
        Sends context prompt and tool schemas to LLM.
        Returns: (text_content: str, tool_calls: List[Dict], raw_response)
        """
        pass

    @abstractmethod
    async def generate_final_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str
    ) -> str:
        """Generates natural language reasoned recommendation text without tool calls."""
        pass