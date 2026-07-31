"""
Mercari Search Manager with Fallback system.
Orchestrates multi-tier execution (WebScraper -> Mercarpi -> Playwright).
"""

import logging
from typing import List, Optional, Dict, Any
from src.data_models.query import MercariItem
from src.backends.mercari.base import BaseMercariSearchTool
from src.backends.mercari.web_scraper import MercariWebSearchTool
from src.config import config

logger = logging.getLogger(__name__)


class MercariSearchManager:
    """Manages multi-tier fallback for Mercari searches."""

    def __init__(self):
        self.tiers: List[BaseMercariSearchTool] = []
        
        # Always register WebSearch
        self.tiers.append(MercariWebSearchTool())

        # Register Tier 2 and Tier 3 based on configuration
        if config.enable_mercari_fallback:
            if config.enable_mercari_fallback_mercarpi:
                try:
                    import mercapi
                    from src.backends.mercari.mercarpi_scraper import MercariMercapiSearchTool
                    self.tiers.append(MercariMercapiSearchTool())
                except ModuleNotFoundError:
                    logger.info("Mercari Mercarpi Module not found")
            if config.enable_mercari_fallback_playwright:
                try:
                    import playwright
                    from src.backends.mercari.playwright_scraper import MercariPlaywrightSearchTool
                    self.tiers.append(MercariPlaywrightSearchTool())
                except ModuleNotFoundError:
                    logger.info("Mercari Playwright Module not found")
        else:
            logger.info("Mercari fallback feature flag is DISABLED. Using WebScraper only.")

    async def search(
        self,
        keyword: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        condition: Optional[str] = None,
        limit: int = 10
    ) -> List[MercariItem]:
        """
        Executes search on Mercari Japan using all registered scraping systems.
        Returns a list of standardized MercariItem instances.
        """
        last_exception = None

        for idx, tool in enumerate(self.tiers, start=1):
            tool_name = tool.__class__.__name__
            try:
                logger.info(f"Executing Mercari Search Tier {idx} ({tool_name})...")
                # Run the search on the actual scraping mecanism
                items = await tool.search(
                    keyword=keyword,
                    min_price=min_price,
                    max_price=max_price,
                    condition=condition,
                    limit=limit
                )

                if items:
                    logger.info(
                        f"Search successfully completed using Tier {idx} ({tool_name}). "
                        f"Retrieved {len(items)} items."
                    )
                    return items            # We got our results, exit the fallback loop

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Tier {idx} ({tool_name}) failed: {e}. "
                    f"Proceeding to next fallback tier..."
                )
                # !Debug: Strictly for debugging full stack trace, DISABLE when not debugging
                #import traceback
                #traceback.print_exc()

        # If all registered tiers fail
        raise RuntimeError(f"All Mercari Search systems failed. Last error: {last_exception}")


    async def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """
        Executes get_item_details across registered scraper tiers.
        Returns Dict[str, Any] with detailed product data.
        """
        for idx, tool in enumerate(self.tiers, start=1):
            try:
                if hasattr(tool, "get_item_details"):
                    details = await tool.get_item_details(item_id)
                    if details:
                        return details
            except Exception as e:
                logger.warning(f"Tier {idx} get_item_details failed for {item_id}: {e}")
                continue

        return {}