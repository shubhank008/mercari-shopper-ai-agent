"""
Priority Scraper: Direct HTTP/API Scraper.
Fetches search results via lightweight HTTP API requests.
"""

import logging
import httpx
import random
import uuid
import time
from httpx import Request
from ecdsa import SigningKey, NIST256p
from typing import List, Optional, Dict, Any
from src.data_models.query import MercariItem
from src.backends.mercari.base import BaseMercariSearchTool
from src.config import config
from src.tools import jwt

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
        self._uuid = str(uuid.UUID(int=random.getrandbits(128)))
        self._key = SigningKey.generate(NIST256p)
        self._client = httpx.AsyncClient()

    # Handle DPoP key signing
    def _sign_request(self, request: Request) -> Request:
        request.headers["DPoP"] = jwt.generate_dpop(
            str(request.url),
            request.method,
            self._key,
            {
                "uuid": self._uuid,
            },
        )
        return request

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

        logger.info(f"[Mercari WebScraper] Searching Mercari JP for keyword: '{keyword}'")

        # !Debug: Disabled API Scraper to test fallbacks
        #raise RuntimeError(f"Mercari WebAPI Scraper is disabled to test fallback systems")

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
            "searchSessionId": uuid.uuid4().hex,            # CANNOT BE EMPTY, RANDOM ID USED
            "indexRouting": "INDEX_ROUTING_UNSPECIFIED",
            "thumbnailTypes": [],
            "searchCondition": {
                "keyword": keyword,
                "excludeKeyword": "",
                "sort": "SORT_SCORE",
                "order": "ORDER_DESC",
                "status": [],
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
            "serviceFrom": "suruga",
            "withItemBrand": True,
            "withItemSize": False,
            "withItemPromotions": True,
            "withItemSizes": True,
            "withShopname": False,
            "useDynamicAttribute": True,
            "withSuggestedItems": True,
            "withOfferPricePromotion": True,
            "withProductSuggest": True,
            "withParentProducts": False,
            "withProductArticles": True,
            "withSearchConditionId": False,
            "withAuction": True,
        }

        # !Debug: For debugging passed values and types, disable in production
        #print(f"[Mercari WebScraper] Payload: '{payload}'")

        # Create Request object
        req = Request(
            "POST",
            self.MERCARI_API_ENDPOINT,
            json=payload,
            headers=self.headers
        )
        signed_req = self._sign_request(req)

        response = await self._client.send(signed_req)

        # !Debug: Save API result to a file for debug
        with open("./web_debug.log", "w", encoding="utf-8") as file:
            #file.write(str(soup))
            file.write(response.text)
        
        if response.status_code != 200:
            logger.info(f"[Mercari WebScraper] Error: {response.text}")
            raise RuntimeError(
                f"Mercari API endpoint returned status HTTP {response.status_code}"
            )

        data = response.json()
        raw_items = data.get("items", [])

        if not raw_items:
            raise ValueError(f"Mercari API returned 0 results for keyword '{keyword}'.")

        # In milliseconds 
        end_time = round((time.perf_counter() - start_time) * 1000, 2)

        items: List[MercariItem] = []
        for item in raw_items[:limit]:
            item_id = item.get("id", "")
            if not item_id:
                continue

            # Condition ID (int) to Value (str)
            conditionId = int(item.get("itemConditionId", "6"))
            # Convert our condition_map dict to list, its index will let us access its key value
            condition_string = list(self.CONDITION_MAP)[conditionId-1] or "any"

            # Item image
            image_url = item.get("thumbnails", [""])[0] if item.get("thumbnails") else None
            # Split and remove the trailing timestamp/identifier in image_url
            image_url = image_url.split("?")[0] if image_url else None

            # !TODO: Mercari search API returns price in JPY only, however provides another endpoint to get exchange-rate for USD
            # /getCurrencyConversionRate/country?country_code=XX

            items.append(
                MercariItem(
                    item_id=item_id,
                    title=item.get("name", f"{keyword} ({item_id})"),
                    price=int(item.get("price", 0)),
                    currency="JPY",
                    price_jpy=int(item.get("price", 0)),
                    price_usd=0,
                    condition=condition_string,
                    item_url=f"https://jp.mercari.com/item/{item_id}",
                    image_url=image_url,
                    description=None,
                    listing_date=float(item.get("updated", 0)),               # Using updated instead of created timestamp
                    source_tier="DirectAPI WebScraper",
                    fetch_time = end_time                  # Not calculating yet
                )
            )

        return items

    #################################
    ## Get detailed product data
    async def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """Fetches detailed item info using Mercari API getItem endpoint."""
        logger.info(f"[Mercari WebScraper] Fetching details for item_id: '{item_id}'")

        # Detailed Parameter URL looks like this
        # https://api.mercari.jp/items/get?id=m98368113851&include_item_attributes=true&include_product_page_component=true&include_non_ui_item_attributes=true&include_donation=true&include_item_attributes_sections=true&include_auction=true&country_code=US
        url = f"https://api.mercari.jp/items/get"

        # Create Request object
        req = Request(
            "GET",
            url,
            params={"id": item_id},
            headers=self.headers
        )
        signed_req = self._sign_request(req)
        response = await self._client.send(signed_req)

        # !Debug: Save get_item API result to a file for debug
        with open("./web_debug.log", "w", encoding="utf-8") as file:
            #file.write(str(soup))
            file.write(response.text)

        if response.status_code == 200:
            data = response.json().get("data", {})
            return {
                "id": item_id,
                "title": data.get("name", ""),
                "price": int(data.get("price", 0)),
                "description": data.get("description", ""),
                "seller_name": data.get("seller", {}).get("name", None),
                "seller_rating_score": data.get("seller", {}).get("star_rating_score", None),
                "seller_total_ratings": data.get("seller", {}).get("num_ratings", None),
                "seller_quick_shipper": data.get("seller", {}).get("quick_shipper", False),
                "price_usd": data.get("converted_price", {}).get("price", None),
                "category": data.get("item_category", {}).get("name", ""),
                "condition": data.get("item_condition", {}).get("name", "Unknown") + " - " + data.get("item_condition", {}).get("subname", ""),
                "listing_date": data.get("updated", None),
                "num_likes": data.get("num_likes", 0),
                "item_url": f"https://jp.mercari.com/item/{item_id}"
            }

        # Fallback dictionary if detail endpoint returns non-200
        return {
            "id": item_id,
            "description": f"",
            "item_url": f"https://jp.mercari.com/item/{item_id}"
        }