"""
Base Interface for Mercari Search Tool backend.
Defines abstract base class and condition code mappers for Mercari searching.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.data_models.query import MercariItem

class BaseMercariSearchTool(ABC):
    """Abstract interface for all Mercari search tool implementations"""

    # Map friendly condition strings to Mercari JP condition query IDs
    CONDITION_MAP = {
        "new": "1",          # 新品、未使用 (New, Unused)
        "like_new": "2",     # 未使用に近い (Like New)
        "good": "3",         # 目立った傷や汚れなし (Good)
        "fair": "4",         # やや傷や汚れあり (Fair)
        "poor": "5",         # 傷や汚れあり (Poor)
        "very_poor": "6",         # 全体的に状態が悪い (Overall Poor)
        "any": ""
    }

    @abstractmethod
    async def search(
        self,
        keyword: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        condition: Optional[str] = None,
        limit: int = 10
    ) -> List[MercariItem]:
        """
        Executes search on Mercari Japan.
        Returns a list of standardized MercariItem instances.
        """
        pass

    @abstractmethod
    async def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """Fetches detailed product listing info (full description, seller ratings, etc.)."""
        pass