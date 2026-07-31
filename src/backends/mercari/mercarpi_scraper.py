"""
Tier 2 Fallback Scraper: Mercari API Scraper using `mercapi`.
Handles dynamic DPoP token generation and request signing required by Mercari.
"""

import logging
import time
from typing import List, Optional, Dict, Any
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

    #################################
    ## Get detailed product data
    async def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """Fetches detailed item info using Mercapi .item() method"""
        logger.info(f"[Mercari MercapiScraper] Fetching details for item_id: '{item_id}'")

        try:
            # Mercapi handles DPoP cryptographic token generation automatically
            item_data = await self.client.item(
                id_=item_id
            )
            
            if not item_data or item_data.id_:
                # Fallback Dict
                return {
                            "id": item_id,
                            "description": f"",
                            "item_url": f"https://jp.mercari.com/item/{item_id}"
                        }

            return {
                        "id": item_id,
                        "title": item_data.name or "",
                        "price": item_data.price or 0,
                        "description": item_data.description or "",
                        "seller_name": item_data.seller.name if item_data.seller else None,
                        "seller_rating_score": item_data.seller.star_rating_score if item_data.seller else None,
                        "seller_total_ratings": item_data.seller.num_ratings if item_data.seller else None,
                        "seller_quick_shipper": item_data.seller.quick_shipper if item_data.seller else False,
                        "price_usd": None,
                        "category": item_data.item_category.name if item_data.item_category else "",
                        "condition": item_data.item_condition.name if item_data.item_condition else "Unknown",
                        "listing_date": item_data.updated.timestamp() if item_data.updated else None,
                        "num_likes": item_data.num_likes or 0,
                        "item_url": f"https://jp.mercari.com/item/{item_id}"
                    }

        except Exception as e:
            logger.warning(f"[Tier 2: MercapiScraper] get_item_details failed: {e}")
            raise RuntimeError(f"MercapiScraper get_item_details execution error: {e}")