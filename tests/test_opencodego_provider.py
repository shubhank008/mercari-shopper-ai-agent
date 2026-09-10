"""Tests for the OpenCode Go compatible provider and manager selection."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from src.config import AppConfig
from src.llm_providers.llm_manager import LLMFallbackManager
from src.llm_providers.opencodego_provider import OpenCodeGoProvider


class RecordingCompletions:
    """Record a compatible completion call and return an OpenAI-shaped response."""

    def __init__(self) -> None:
        self.kwargs = None

    async def create(self, **kwargs):
        """Return a function-call completion without contacting an external service."""
        self.kwargs = kwargs
        tool_call = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="search_mercari", arguments='{"keyword":"Seiko 5"}'),
        )
        message = SimpleNamespace(content="", tool_calls=[tool_call])
        usage = SimpleNamespace(prompt_tokens=12, completion_tokens=8)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class RecordingClient:
    """Minimal OpenAI-compatible client surface used by the provider."""

    def __init__(self) -> None:
        self.completions = RecordingCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class OpenCodeGoProviderTests(unittest.TestCase):
    """Verify request construction and parsing without an API key or live endpoint."""

    def test_tool_call_uses_openai_compatible_contract(self) -> None:
        """Send the configured model, system message, tools, timeout, and parse calls."""
        client = RecordingClient()
        with patch("src.llm_providers.opencodego_provider.config") as provider_config:
            provider_config.opencodego_api_key = "test-key"
            provider_config.opencodego_model_id = "glm-5.3-flash"
            provider_config.opencodego_base_url = "https://opencode.ai/zen/go/v1"
            provider_config.llm_timeout_seconds = 15.0
            provider = OpenCodeGoProvider(client=client)
            text, calls, usage, _ = asyncio.run(
                provider.generate_tool_call(
                    messages=[{"role": "user", "content": "Find a Seiko"}],
                    tools=[{
                        "name": "search_mercari",
                        "description": "Search listings.",
                        "input_schema": {"type": "object", "properties": {"keyword": {"type": "string"}}},
                    }],
                    system_prompt="You are a shopper.",
                )
            )

        self.assertEqual(text, "")
        self.assertEqual(calls, [{"id": "call_1", "name": "search_mercari", "arguments": {"keyword": "Seiko 5"}}])
        self.assertEqual(usage, {"input_tokens": 12, "output_tokens": 8})
        self.assertEqual(client.completions.kwargs["model"], "glm-5.3-flash")
        self.assertEqual(client.completions.kwargs["messages"][0], {"role": "system", "content": "You are a shopper."})
        self.assertEqual(client.completions.kwargs["tools"][0]["type"], "function")
        self.assertEqual(client.completions.kwargs["timeout"], 15.0)

    def test_multi_turn_anthropic_blocks_are_normalized_for_openai_api(self) -> None:
        """Serialize assistant tool calls and tool results as OpenAI messages."""
        client = RecordingClient()
        messages = [
            {"role": "user", "content": "Find an iPhone 16."},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I will search."},
                    {"type": "tool_use", "id": "call_1", "name": "search_mercari", "input": {"keyword": "iPhone 16"}},
                    {"type": "tool_use", "id": "call_2", "name": "search_mercari", "input": {"keyword": "iPhone16 本体"}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": "first results"},
                    {"type": "tool_result", "tool_use_id": "call_2", "content": "second results"},
                ],
            },
        ]
        with patch("src.llm_providers.opencodego_provider.config") as provider_config:
            provider_config.opencodego_api_key = "test-key"
            provider_config.opencodego_model_id = "glm-5.2"
            provider_config.opencodego_base_url = "https://opencode.ai/zen/go/v1"
            provider_config.llm_timeout_seconds = 15.0
            provider = OpenCodeGoProvider(client=client)
            asyncio.run(provider.generate_tool_call(messages, [], "You are a shopper."))

        sent = client.completions.kwargs["messages"]
        self.assertEqual(sent[2]["role"], "assistant")
        self.assertEqual(sent[2]["content"], "I will search.")
        self.assertEqual(len(sent[2]["tool_calls"]), 2)
        self.assertEqual(sent[2]["tool_calls"][0]["function"]["name"], "search_mercari")
        self.assertEqual(sent[3], {"role": "tool", "tool_call_id": "call_1", "content": "first results"})
        self.assertEqual(sent[4], {"role": "tool", "tool_call_id": "call_2", "content": "second results"})


    def test_invalid_primary_provider_is_rejected(self) -> None:
        """Fail fast when a deployment selects an unsupported provider name."""
        with self.assertRaises(ValidationError):
            AppConfig(llm_primary_provider="unsupported")

    def test_manager_initializes_selected_provider_before_fallbacks(self) -> None:
        """Keep the configured primary ahead of deterministic compatible fallbacks."""
        initialized = []

        class Provider:
            def __init__(self, name: str) -> None:
                self.provider_name = name

        factories = {
            "anthropic": lambda: initialized.append("anthropic") or Provider("anthropic"),
            "openai": lambda: initialized.append("openai") or Provider("openai"),
            "opencodego": lambda: initialized.append("opencodego") or Provider("opencodego"),
        }
        with patch.object(LLMFallbackManager, "_provider_factories", factories), patch(
            "src.llm_providers.llm_manager.config"
        ) as manager_config:
            manager_config.llm_primary_provider = "opencodego"
            manager_config.enable_llm_fallback = True
            manager = LLMFallbackManager()

        self.assertEqual(initialized, ["opencodego", "anthropic", "openai"])
        self.assertEqual([provider.provider_name for provider in manager.providers], initialized)


if __name__ == "__main__":
    unittest.main()
