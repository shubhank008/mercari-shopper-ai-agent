"""
Tier 2 Fallback Scraper: Mercari API Scraper using `mercapi`.
Handles dynamic DPoP token generation and request signing required by Mercari.
"""

import logging
import time
from typing import List, Optional
from mercapi import Mercapi
from src.data_models.query import MercariItem
from src.backends.mercari.base import BaseMercariSearchTool

logger = logging.getLogger(__name__)


class MercariMercapiSearchTool(BaseMercariSearchTool):
    """Tier 2 Fallback Scraper using mercapi wrapper for authenticated Mercari JP requests."""

    def __init__(self):
        self.client = Mercapi()

    async def search(
        self,
        keyword: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        condition: Optional[str] = None,
        limit: int = 10
    ) -> List[MercariItem]:
        # !Debug: For calculating execution time for performance benchmarks
        start_time = time.perf_counter()

        logger.info(f"[Mercari MercapiScraper] Querying Mercari JP for keyword: '{keyword}'")

        # Map condition string to API condition IDs
        cond_ids = []
        if condition and condition in self.CONDITION_MAP:
            cid = self.CONDITION_MAP[condition]
            if cid and cid.isdigit():
                cond_ids.append(int(cid))

        try:
            # Mercapi handles DPoP cryptographic token generation automatically
            results = await self.client.search(
                query=keyword, 
                price_min=min_price or 0,
                price_max=max_price or 0,
                item_conditions=cond_ids
            )
            
            if not results or not results.items:
                raise ValueError(f"Mercari MercapiScraper returned 0 results for keyword '{keyword}'.")

            # In milliseconds 
            end_time = round((time.perf_counter() - start_time) * 1000, 2)

            items: List[MercariItem] = []
            
            for item in results.items:
                if len(items) >= limit:
                    break

                price = int(item.price) if item.price else 0

                 # Condition ID (int) to Value (str)
                conditionId = int(item.item_condition_id or "6")
                # Convert our condition_map dict to list, its index will let us access its key value
                condition_string = list(self.CONDITION_MAP)[conditionId-1] or "any"

                # Item image
                image_url = item.thumbnails[0] if item.thumbnails else None
                # Split and remove the trailing timestamp/identifier in image_url
                image_url = image_url.split("?")[0] if image_url else None

                item_id = str(item.id_)
                items.append(
                    MercariItem(
                        item_id=item_id,
                        title=item.name or f"{keyword} ({item_id})",
                        price=price,
                        currency="JPY",
                        price_jpy=price,
                        price_usd=0,
                        condition=condition_string,
                        item_url=f"https://jp.mercari.com/item/{item_id}",
                        image_url=image_url,
                        description=None,
                        listing_date=float(item.updated.timestamp() if item.updated else 0),               # Using updated instead of created timestamp
                        source_tier="Mercari MercapiScraper",
                        fetch_time = end_time                  # Not calculating yet
                    )
                )

            if not items:
                raise ValueError(
                    f"Zero items matched the criteria after price filtering (¥{min_price or 0} - ¥{max_price or 'Unbounded'})."
                )

            return items

        except Exception as e:
            logger.warning(f"[Tier 2: MercapiScraper] Search failed: {e}")
            raise RuntimeError(f"MercapiScraper execution error: {e}")