"""
Core Agent Harness, the brain of our shopping engine.
Manages tool-calling, execution, state machine, provider failovers and session context.
"""

import json
import logging
from typing import List, Dict, Any, Tuple
from src.llm_providers.llm_manager import LLMFallbackManager
from src.backends.mercari.mercari_search import MercariSearchManager
from src.guardrails.safety import PromptGuardrail, ContextSanitizer
from src.agent.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from src.data_models.query import MercariItem, AgentState
from src.config import config

logger = logging.getLogger(__name__)


class AgentHarness:
    """Agent Harness runtime - controlling tool loops and session state."""

    def __init__(self):
        self.llm_manager = LLMFallbackManager()
        self.search_manager = MercariSearchManager()
        
        # Tool Registry and Mapping
        # !TODO: Probably will need to add a RAG tool to get item details
        self.tool_registry = {
            "search_mercari": self._execute_search_tool
        }

    async def _execute_search_tool(self, **kwargs) -> Tuple[List[MercariItem], str]:
        """Tool execution handler for Mercari searching."""

        keyword = kwargs.get("keyword", "")
        min_price = kwargs.get("min_price", 0)
        max_price = kwargs.get("max_price", 0)
        condition = kwargs.get("condition", None)

        # Actual function calling, our MercariSearchManager will internally handle the Fallbacks
        items = await self.search_manager.search(
            keyword=keyword,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            limit=config.max_items_per_search
        )
        
        tier_used = items[0].source_tier if items else "Unknown"
        return items, tier_used

    ############################
    ## MAIN Loop
    ###########################
    async def run(self, user_prompt: str) -> Tuple[str, List[MercariItem], str, str]:
        """
        Executes autonomous agent loop for a user query.
        Returns: (final_recommendation_text, retrieved_items, active_provider, active_tier)
        """

        # Safety Guardrail Inspection
        is_safe, warning_msg = PromptGuardrail.validate_prompt(user_prompt)
        if not is_safe:
            return warning_msg, [], "Guardrail", "None"

        # Prompt Builder
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_prompt}
        ]

        retrieved_items: List[MercariItem] = []
        active_tier = "None"
        active_provider = "Unknown"

        # Tool-Calling State Loop
        # 
        for loop_count in range(config.max_tool_call_loops):
            logger.info(f"Mercari Agent Harness Loop - Turn {loop_count + 1}/{config.max_tool_call_loops}")

            # Send System Prompt, User Prompt and tool definitions to LLM
            # This step extracts us the product keyword and other parameters from user prompt for Tool Calling (mercari_search)
            # raw_resp can be used for Debug
            text_content, tool_calls, raw_resp, provider = await self.llm_manager.generate_tool_call(
                messages=messages,
                tools=TOOL_DEFINITIONS,
                system_prompt=SYSTEM_PROMPT
            )
            active_provider = provider

            # If LLM generated text without requesting tool calls, loop ends
            # retrieved_items is empty here
            if not tool_calls:
                return text_content, retrieved_items, active_provider, active_tier

            # Process All Tool Call Requests
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                tool_id = tool_call["id"]

                logger.info(f"LLM requested tool execution: '{tool_name}' with args: {tool_args}")

                # Make sure tool is registered in our registry
                if tool_name in self.tool_registry:
                    # Execute tool locally in Python
                    items, tier_used = await self.tool_registry[tool_name](**tool_args)
                    retrieved_items = items
                    active_tier = tier_used

                    # Format and sanitize item data for LLM context
                    item_dicts = [item.model_dump() for item in items]
                    sanitized_dicts = ContextSanitizer.prepare_items_for_context(
                        item_dicts, max_length=config.max_description_length
                    )

                    # Inject Assistant message turn and Tool Result turn into context
                    messages.append({
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tool_id,
                                "name": tool_name,
                                "input": tool_args
                            }
                        ]
                    })

                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": json.dumps(sanitized_dicts, ensure_ascii=False)
                            }
                        ]
                    })
                else:
                    # We donot let the agent proceed ahead if our Tool was not found or registered as its a technical lapse
                    # And also means LLM would just generate a FalsePositive recommendation based entirely on User's initial prompt, 
                    # with 0 product details from our end
                    # !TODO: Good idea to add automated Issue/Incident logging here
                    return "Mercari Product fetching is currently unavailable", [], "ToolRegistry", "None"

            # 4. Generate Final Reasoned Recommendation
            final_text, provider = await self.llm_manager.generate_final_response(
                messages=messages,
                system_prompt=SYSTEM_PROMPT
            )
            active_provider = provider
            return final_text, retrieved_items, active_provider, active_tier

        return "Task execution reached maximum loop limit.", retrieved_items, active_provider, active_tier