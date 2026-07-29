"""
Priority Scraper: Direct HTTP/Web Scraper.
Fetches search results via lightweight HTTP requests.
"""

import logging
import httpx
from typing import List, Optional
from src.data_models.query import MercariItem
from src.backends.mercari.base import BaseMercariSearchTool
from src.config import config

logger = logging.getLogger(__name__)


class MercariWebSearchTool(BaseMercariSearchTool):
    """Attempt scraping using direct HTTP search queries."""

    MERCARI_SEARCH_URL = "https://jp.mercari.com/search"

    def __init__(self):
        # Fake browser headers and user-agent
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def search(
        self,
        keyword: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        condition: Optional[str] = None,
        limit: int = 10
    ) -> List[MercariItem]:
        logger.info(f"[Mercari WebScraper] Searching Mercari JP for keyword: '{keyword}'")

        params = {"keyword": keyword}
        if min_price is not None:
            params["price_min"] = str(min_price)
        if max_price is not None:
            params["price_max"] = str(max_price)
        if condition and condition in self.CONDITION_MAP:
            cond_id = self.CONDITION_MAP[condition]
            if cond_id:
                params["item_condition_id"] = cond_id

        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=config.request_timeout_seconds
        ) as client:
            response = await client.get(self.MERCARI_SEARCH_URL, params=params)
            
            if response.status_code != 200:
                raise RuntimeError(
                    f"Mercari API endpoint returned status HTTP {response.status_code}"
                )

            # Parse HTML DOM / embedded JSON script tags
            # If response HTML lacks rendered items (due to client-side JS requirement), trigger fallback
            items = self._parse_response_body(response.text, limit=limit)
            
            if not items:
                raise ValueError("Mercari WebScraper returned 0 items (JS rendering likely required).")

            return items

    def _parse_response_body(self, html_content: str, limit: int) -> List[MercariItem]:
        """Parses HTML content for embedded JSON listing data or item elements."""
        # Local import, only when needed
        from bs4 import BeautifulSoup
        import json
        import re

        items = []
        soup = BeautifulSoup(html_content, "html.parser")

        # !Debug: Save html content to a file for debug
        with open("./debug.html", "w", encoding="utf-8") as file:
            #file.write(str(soup))
            file.write(soup.prettify())

        # Attempt to find Mercari's embedded state script tag
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if script_tag and script_tag.string:
            try:
                data = json.loads(script_tag.string)
                # Walk through Next.js state tree for search items
                search_results = (
                    data.get("props", {})
                    .get("pageProps", {})
                    .get("initialState", {})
                    .get("search", {})
                    .get("items", [])
                )

                for raw_item in search_results[:limit]:
                    item_id = raw_item.get("id", "")
                    if not item_id:
                        continue
                    
                    items.append(
                        MercariItem(
                            item_id=item_id,
                            title=raw_item.get("name", "Mercari Listing"),
                            price=int(raw_item.get("price", 0)),
                            condition=raw_item.get("conditionName", "Used"),
                            item_url=f"https://jp.mercari.com/item/{item_id}",
                            image_url=raw_item.get("thumbnails", [""])[0] if raw_item.get("thumbnails") else None,
                            description=raw_item.get("description", ""),
                            source_tier="Tier 1: Direct API"
                        )
                    )
            except Exception as e:
                logger.debug(f"Failed to parse __NEXT_DATA__ script: {e}")

        return items