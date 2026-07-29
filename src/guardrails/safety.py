"""
Guardrails and Safety Module.
Protects against prompt injections and sanitizes raw scraped tool data.
"""

import re
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


# Detects malicious prompt injection or jailbreak attempts in user input.
class PromptGuardrail:

    # !TODO: It might be better to use a mature library to handle the guard-rails instead of relying on pattern-matching
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?prior\s+prompts",
        r"system\s+prompt\s+override",
        r"you\s+are\s+now\s+a\s+DAN",
        r"output\s+your\s+system\s+instructions",
        r"forget\s+everything\s+you\s+know",
    ]

    # Validates user prompt string against security rules
    # Returns: (is_safe: bool, warning_message: str)
    @classmethod
    def validate_prompt(cls, prompt: str) -> Tuple[bool, str]:

        if not prompt or not prompt.strip():
            return False, "Empty Message sent, Please enter your shopping query."

        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                logger.warning(f"Prompt injection pattern detected: {pattern}")
                return False, (
                    "Security Warning: Message contains unauthorized or malicious content. "
                    "Please rephrase your shopping query."
                )

        return True, ""


# Sanitizes outputs and raw scraped listing data before context injection.
class ContextSanitizer:

    # Strips HTML tags, trims whitespace, and truncates text length.
    @staticmethod
    def sanitize_description(text: str, max_length: int = 200) -> str:

        if not text:
            return ""

        # Remove HTML tags
        clean_text = re.sub(r"<[^>]+>", "", text)
        # Collapse multiple whitespace/newlines
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        if len(clean_text) > max_length:
            return clean_text[:max_length] + "..."

        return clean_text

    # Sanitizes a list of retrieved Mercari item dicts for injection into LLM messages.
    @classmethod
    def prepare_items_for_context(cls, items: List[Dict[str, Any]], max_length: int = 200) -> List[Dict[str, Any]]:

        sanitized_items = []
        for item in items:
            clean_item = item.copy()
            if "description" in clean_item:
                clean_item["description"] = cls.sanitize_description(
                    clean_item["description"], max_length=max_length
                )
            sanitized_items.append(clean_item)

        return sanitized_items