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
    """Agent Harness runtime controlling multi-step tool loops and session state."""

    def __init__(self):
        self.llm_manager = LLMFallbackManager()
        self.search_manager = MercariSearchManager()
        
        # Tool Registry and Mapping
        # !TODO: Probably will need to add a RAG tool to get item details
        self.tool_registry = {
            "search_mercari": self._execute_search_tool,
            "get_item_details": self._execute_item_details_tool
        }

    async def _execute_search_tool(self, **kwargs) -> Tuple[List[MercariItem], str]:
        """Tool execution handler for Mercari product searching."""

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

    async def _execute_item_details_tool(self, **kwargs) -> Tuple[List[Dict[str, Any]], str]:
        """Tool execution handler for fetching item details for candidate IDs."""
        item_ids = kwargs.get("item_ids", [])
        # If single id was passed as string, turn to list
        if isinstance(item_ids, str):
            item_ids = [item_ids]

        detailed_items: List[Dict[str, Any]] = []
        for item_id in item_ids:
            details = await self.search_manager.get_item_details(item_id)
            if details:
                detailed_items.append(details)

        return detailed_items, "ItemDetails Scraper"
    

    ############################
    ## MAIN Loop
    ###########################
    async def run(self, user_prompt: str) -> Tuple[str, List[MercariItem], str, str]:
        """
        Executes autonomous agent loop across multiple reasoning turns for the user's query.
        Returns: (final_recommendation_text, retrieved_items, active_provider, active_tier)
        """

        # Safety Guardrail Check
        is_safe, warning_msg = PromptGuardrail.validate_prompt(user_prompt)
        if not is_safe:
            return warning_msg, [], "Guardrail", "None"

        # Prompt Builder
        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_prompt}
        ]

        # Single Source of Truth for Session State
        # search_mercari fetches us partial data, which we hydrate with detailed data from get_item_data
        retrieved_items_map: Dict[str, MercariItem] = {}
        active_tier = "None"
        active_provider = "Unknown"

        # Tool-Calling and Multi-Turn State Loop
        # Agent manages initial response, tool_calls and final response through Turn-based step loops
        # This allows LLM to see updated messages/results on next turn and decide if it wants to execute another tool_call, self-correct or read for final response
        # !TODO: We have implemented Sequential Tool Chaining, but there is scope to add Self-Correction on Tool Failure too
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

            # -------------------------------------------------------------
            # EXIT POINT: If tool_calls is empty, LLM generated final response!
            # -------------------------------------------------------------
            if not tool_calls:
                logger.info(f"{provider} returned text without requesting tool calls. State loop completed, RETURNING RESULTS.")
                retrieved_items = list(retrieved_items_map.values())
                return text_content, retrieved_items, active_provider, active_tier

            # Record tool request in message history for assistant message turn
            assistant_content = []
            if text_content:
                assistant_content.append({"type": "text", "text": text_content})
            
            for tc in tool_calls:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"]
                })
            
            messages.append({"role": "assistant", "content": assistant_content})

            # MAJOR - Execute Requested Tools and Build Tool Result Message Turn
            tool_results_content = []
            # Process All Tool Call Requests
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                tool_id = tool_call["id"]

                logger.info(f"[Harness] Agent executing tool: '{tool_name}' with args: {tool_args}")

                # Moved tool calling in a try block just in case a exception or failure happens
                # and to gracefully handle it and show message on user side
                try:
                    # Make sure tool is registered in our registry
                    if tool_name == "search_mercari":
                        ## Actual Tool Calling
                        items, tier_used = await self.tool_registry[tool_name](**tool_args)
                        active_tier = tier_used

                        # Store newly discovered search items in session map
                        for item in items:
                            if item.item_id not in retrieved_items_map:
                                retrieved_items_map[item.item_id] = item

                        # Format and sanitize item data for LLM context
                        item_dicts = [item.model_dump() for item in items]                      # Pydantic model to Dict
                        sanitized_dicts = ContextSanitizer.prepare_items_for_context(
                            item_dicts, max_length=config.max_description_length
                        )
                        result_payload = json.dumps(sanitized_dicts, ensure_ascii=False)
                    elif tool_name == "get_item_details":
                        ## Actual Tool Calling
                        detailed_items, tier_used = await self.tool_registry[tool_name](**tool_args)
                        active_tier = tier_used

                        # Hydrate existing MercariItem sessions map with these extra item details
                        context_payload_list = []
                        for detailed_item in detailed_items:
                            item_id = detailed_item.get("id")
                            if item_id in retrieved_items_map:
                                existing_item = retrieved_items_map[item_id]
                                retrieved_items_map[item_id] = existing_item.model_copy(update=detailed_item)      # Pydantic validation and update existing model using dict
                                context_payload_list.append(retrieved_items_map[item_id].model_dump())

                        # Format and sanitize item data for LLM context
                        sanitized_dicts = ContextSanitizer.prepare_items_for_context(
                            context_payload_list, max_length=config.max_description_length
                        )
                        result_payload = json.dumps(sanitized_dicts, ensure_ascii=False)
                    else:
                        # We donot let the agent proceed ahead if our Tool was not found or registered as its a technical lapse
                        # And also means LLM would just generate a FalsePositive recommendation based entirely on User's initial prompt, 
                        # with 0 product details from our end
                        # !TODO: Good idea to add automated Issue/Incident logging here
                        result_payload = json.dumps({"error": f"Mercari Product fetching is currently unavailable, as '{tool_name}' is not registered."})
                except Exception as e:
                    # Pass execution error BACK to LLM so it can attempt self-correction!
                    logger.warning(f"[Harness] Tool '{tool_name}' execution failed: {e}")
                    result_payload = json.dumps({"error": f"Search failed: {str(e)}. Try adjusting keywords, pricing, condition or other filters."})

                # Prepare Tool Execution results for context
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_payload
                })

            # This way we append success or failure of one or multiple tools into the context
            # So next step-turn LLM can decide if it achieved desired results or need to self-correct and run another turn
            messages.append({"role": "user", "content": tool_results_content})

            # CRITICAL: NO RETURN HERE!
            # The multi-step loop iterates to Turn 2. The LLM receives updated `messages` with tool_call results appended
            # and evaluates whether to issue another tool call or complete the request with appended data.

            # Old way using single turn and chained calls
            # Generate Final Reasoned Recommendation
            #final_text, provider = await self.llm_manager.generate_final_response(
            #    messages=messages,
            #    system_prompt=SYSTEM_PROMPT
            #)
            #active_provider = provider
            #return final_text, retrieved_items, active_provider, active_tier
        final_items = list(retrieved_items_map.values())
        return "Agent reached maximum step-turns limit", retrieved_items, active_provider, active_tier