"""
Base LLM Provider Interface.
Defines standard abstract interface for Anthropic, OpenAI, and any future LLM backends (openrouter / openweight).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple


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