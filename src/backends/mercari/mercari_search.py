"""
Mercari Search Manager with Fallback system.
Orchestrates multi-tier execution (WebScraper -> Mercarpi -> Playwright).
"""

import logging
from typing import List, Optional
from src.data_models.query import MercariItem
from src.backends.mercari.base import BaseMercariSearchTool
from src.backends.mercari.web_scraper import MercariWebSearchTool
#from src.backends.mercari.playwright_scraper import PlaywrightSearchTool
#from src.backends.mercari.mercarpi_scraper import MercarpiSearchTool
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
                    from src.backends.mercari.mercarpi_scraper import MercarpiSearchTool
                    self.tiers.append(MercarpiSearchTool())
                except ModuleNotFoundError:
                    logger.info("Mercari Mercarpi Module not found")
            if config.enable_mercari_fallback_playwright:
                try:
                    from src.backends.mercari.playwright_scraper import PlaywrightSearchTool
                    self.tiers.append(PlaywrightSearchTool())
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

        # If all registered tiers fail
        raise RuntimeError(f"All Mercari Search systems failed. Last error: {last_exception}")