"""
Core Agent Harness, the brain of our shopping engine.
Manages tool-calling, execution, state machine, provider failovers and session context.
"""

import json
import logging
import time
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
        self.start_time = time.perf_counter()
        self.llm_manager = LLMFallbackManager()
        self.search_manager = MercariSearchManager()
        
        # Tool Registry and Mapping
        # !TODO: Probably will need to add a RAG tool to get item details
        self.tool_registry = {
            "search_mercari": self._execute_search_tool,
            "get_item_details": self._execute_item_details_tool
        }

        # Persistent Session Memory
        self.conversation_history: List[Dict[str, Any]] = []
        # Single Source of Truth for Session State
        # search_mercari fetches us partial data, which we hydrate with detailed data from get_item_data
        self.session_items_map: Dict[str, MercariItem] = {}
        self.enriched_item_ids: set[str] = set()

        init_duration_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        logger.info(f"Agent Harness Initialization Completed in {init_duration_ms}ms")

    def reset_session(self):
        """Clears active session conversation memory and items map."""
        self.conversation_history = []
        self.session_items_map = {}
        self.enriched_item_ids = set()
        logger.info("Session conversation memory reset.")

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
    async def run(self, user_prompt: str) -> Tuple[str, List[MercariItem], str, str, Dict[str, Any]]:
        """
        Executes autonomous agent loop across multiple reasoning turns for the user's query.
        Returns: (final_recommendation_text, retrieved_items, active_provider, active_tier)
        """
        self.start_time = time.perf_counter()

        # Safety Guardrail Check
        is_safe, warning_msg = PromptGuardrail.validate_prompt(user_prompt)
        if not is_safe:
            return warning_msg, [], "Guardrail", "None", {"total_duration_ms": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_turns": 0}

        # Session Memory Management
        if config.enable_session_memory and self.conversation_history:
            self.conversation_history.append({"role": "user", "content": user_prompt})
            messages = self.conversation_history
        else:
            messages = [{"role": "user", "content": user_prompt}]
            if config.enable_session_memory:
                self.conversation_history = messages

        active_tier = "None"
        active_provider = "Unknown"
        total_input_tokens = 0
        total_output_tokens = 0

        # Reset message history of sessions memory is not enabled
        if not config.enable_session_memory:
            self.reset_session()

        # Tool-Calling and Multi-Turn State Loop
        # Agent manages initial response, tool_calls and final response through Turn-based step loops
        # This allows LLM to see updated messages/results on next turn and decide if it wants to execute another tool_call, self-correct or read for final response
        # !TODO: We have implemented Sequential Tool Chaining, but there is scope to add Self-Correction on Tool Failure too
        for loop_count in range(config.max_tool_call_loops):
            logger.info(f"Mercari Agent Harness Loop - Turn {loop_count + 1}/{config.max_tool_call_loops}")
            turn_llm_start = time.perf_counter()

            # Send System Prompt, User Prompt and tool definitions to LLM
            # This step extracts us the product keyword and other parameters from user prompt for Tool Calling (mercari_search)
            # raw_resp can be used for Debug
            text_content, tool_calls, token_usage, raw_resp, provider = await self.llm_manager.generate_tool_call(
                messages=messages,
                tools=TOOL_DEFINITIONS,
                system_prompt=SYSTEM_PROMPT
            )
            llm_turn_ms = round((time.perf_counter() - turn_llm_start) * 1000, 2)
            active_provider = provider

            # Accumulate Token Usage
            in_tok = token_usage.get("input_tokens", 0)
            out_tok = token_usage.get("output_tokens", 0)
            total_input_tokens += in_tok
            total_output_tokens += out_tok

            logger.info(
                f"[Turn {loop_count + 1} Metrics] Latency: {llm_turn_ms}ms | "
                f"Tokens: {in_tok} in / {out_tok} out"
            )

            # -------------------------------------------------------------
            # EXIT POINT: If tool_calls is empty, LLM generated final response!
            # -------------------------------------------------------------
            if not tool_calls:
                logger.info(f"{provider} returned text without requesting tool calls. State loop completed, RETURNING RESULTS.")
                # Append agent final response to conversation memory
                if config.enable_session_memory:
                    self.conversation_history.append({"role": "assistant", "content": text_content})

                total_duration_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
                metrics = {
                    "total_duration_ms": total_duration_ms,
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_turns": loop_count + 1
                }
                logger.info(
                    f"[SESSION SUMMARY] Duration: {total_duration_ms}ms | "
                    f"Total Tokens: {total_input_tokens + total_output_tokens}"
                )

                retrieved_items = list(self.session_items_map.values())
                return text_content, retrieved_items, active_provider, active_tier, metrics

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
                            if item.item_id not in self.session_items_map:
                                self.session_items_map[item.item_id] = item

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
                            if item_id in self.session_items_map:
                                existing_item = self.session_items_map[item_id]
                                updated_item = existing_item.model_dump()
                                updated_item.update({key: value for key, value in detailed_item.items() if value is not None})
                                self.session_items_map[item_id] = MercariItem.model_validate(updated_item)
                                self.enriched_item_ids.add(item_id)
                                context_payload_list.append(self.session_items_map[item_id].model_dump())

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
        
        total_duration_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        metrics = {
            "total_duration_ms": total_duration_ms,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }
        final_items = list(self.session_items_map.values())
        return "Agent reached maximum step-turns limit", final_items, active_provider, active_tier, metrics