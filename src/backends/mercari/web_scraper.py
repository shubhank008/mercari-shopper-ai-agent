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

    MERCARI_API_ENDPOINT = "https://api.mercari.jp/v2/entities:search"

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
            "Content-Type": "application/json",
            "X-Platform": "web",
            "Origin": "https://jp.mercari.com",
            "Referer": "https://jp.mercari.com/",
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

        # Map condition string to API condition IDs
        cond_ids = []
        if condition and condition in self.CONDITION_MAP:
            cid = self.CONDITION_MAP[condition]
            if cid and cid.isdigit():
                cond_ids.append(int(cid))

        # Payload structure required by https://api.mercari.jp/v2/entities:search
        payload = {
            "userId": "",
            "pageSize": limit,
            "pageToken": "",
            "searchSessionId": "",
            "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
            "thumbnailTypes": [],
            "searchCondition": {
                "keyword": keyword,
                "excludeKeyword": "",
                "sort": "SORT_SCORE",
                "order": "ORDER_DESC",
                "status": ["STATUS_ON_SALE"],
                "sizeId": [],
                "categoryId": [],
                "brandId": [],
                "sellerId": [],
                "priceMin": min_price or 0,
                "priceMax": max_price or 0,
                "itemConditionId": cond_ids,
                "shippingPayerId": []
            },
            "defaultSearchCondition": {},
            "serviceFrom": "suruga"
        }

        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=config.request_timeout_seconds
        ) as client:
            response = await client.post(self.MERCARI_API_ENDPOINT, json=payload)

            # !Debug: Save API result to a file for debug
            with open("./web_debug.log", "w", encoding="utf-8") as file:
                #file.write(str(soup))
                file.write(response.text)
            
            if response.status_code != 200:
                raise RuntimeError(
                    f"Mercari API endpoint returned status HTTP {response.status_code}"
                )

            data = response.json()
            raw_items = data.get("items", [])

            if not raw_items:
                raise ValueError(f"Mercari API returned 0 results for keyword '{keyword}'.")

            items: List[MercariItem] = []
            for item in raw_items[:limit]:
                item_id = item.get("id", "")
                if not item_id:
                    continue

                items.append(
                    MercariItem(
                        item_id=item_id,
                        title=item.get("name", "Mercari Item"),
                        price=int(item.get("price", 0)),
                        condition=item.get("itemConditionId", "Used"),
                        item_url=f"https://jp.mercari.com/item/{item_id}",
                        image_url=item.get("thumbnails", [""])[0] if item.get("thumbnails") else None,
                        description=f"Mercari listing for {item.get('name')}.",
                        source_tier="DirectAPI WebScraper",
                        fetch_time = 0                  # Not calculating yet
                    )
                )

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