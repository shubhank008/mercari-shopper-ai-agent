"""
Fallback Scraper: Playwright Headless Browser Scraper.
Waits for Next.js App Router client-side hydration to render product grid cells.
"""

import logging
import re
from typing import List, Optional, Tuple
from playwright.async_api import async_playwright
from src.data_models.query import MercariItem
from src.backends.mercari.base import BaseMercariSearchTool
from src.config import config

logger = logging.getLogger(__name__)


class PlaywrightSearchTool(BaseMercariSearchTool):
    """Fallback Scraper using Playwright headless Chromium browser."""

    async def search(
        self,
        keyword: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        condition: Optional[str] = None,
        limit: int = 10
    ) -> List[MercariItem]:
        logger.info(f"[Tier 2: Playwright] Launching Chromium for keyword: '{keyword}'")

        search_url = f"https://jp.mercari.com/search?keyword={keyword}"
        if min_price is not None:
            search_url += f"&price_min={min_price}"
        if max_price is not None:
            search_url += f"&price_max={max_price}"
        if condition is not None:
            search_url += f"&item_condition={condition}"

        items: List[MercariItem] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )
                # Set user-agent and other headers
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="ja-JP"
                )
                page = await context.new_page()

                # Navigate to page
                await page.goto(search_url, wait_until="networkidle", timeout=config.request_timeout_seconds * 1000)

                # !Debug: Clear previous log result
                with open("./playwright_debug.log", "w") as file:
                    pass  # 'pass' does nothing, leaving the file completely empty

                # Wait for rendered item cell links
                # We are using Dom selector for first item cell, which should be available once page is finished loading/rendering
                # !TODO: Probably a good idea to configure the DOM selector in .env as well so its easier and faster to update it if Mercari changes the ID
                try:
                    await page.wait_for_selector("a[data-testid='thumbnail-link']", timeout=8000)
                except Exception:
                    # !Debug: Save page element output incase DOM Extraction fails
                    with open("./playwright_debug.log", "w") as file:
                        file.write(await page.inner_html("html"))
                    logger.warning("[Mercari PlaywrightScraper] Selector wait timed out, attempting DOM extraction anyway.")

                # Extract listing links
                elements = await page.query_selector_all("a[data-testid='thumbnail-link']")

                # !Debug: Save Playright DOM result to a file for debug
                # We can use the saved raw html of item in DOM Viewer to easily analyze the DOM structure if Mercari Updates/Breaks it 
                if len(elements) > 0:
                    logger.warning(f"[Mercari PlaywrightScraper] Fetched items: {len(elements)}, limit: {limit}")
                    with open("./playwright_debug.log", "w", encoding="utf-8") as file:
                        #file.write(str(soup))
                        file.write(await elements[0].inner_html())
                
                for idx, el in enumerate(elements[:limit]):
                    try:
                        href = await el.get_attribute("href") or ""
                        item_id = href.split("/")[-1] if href else f"pw_{idx}"

                        # Extract aria-label or title text
                        title_el = await el.query_selector("[class*='itemName'], [data-testid='thumbnail-item-name']")
                        title = await title_el.inner_text() if title_el else f"Mercari Listing {item_id}"

                        # Extract aria-label attribute from element or parent/child
                        aria_label_el = await el.query_selector("div[class*='merItemThumbnail']") or None
                        aria_label = await aria_label_el.get_attribute("aria-label") if aria_label_el else None

                        # Parse Currency, Price_Raw, Price_JPY, Price_USD via Regex
                        currency_text, clean_price, jpy, usd = self._extract_price(aria_label)

                        # Fallback for Price & Currency if regex failed
                        # We pass the parent element to fallback method
                        if not currency_text or clean_price == 0:
                            currency_text, clean_price, jpy, usd = self._extract_price_fallback(el)
                        
                        # Extract image url
                        image_el = await el.query_selector("img") or None
                        image_url = await image_el.get_attribute("src") if image_el else None
                        # Split and remove the trailing timestamp/identifier in image_url
                        image_url = image_url.split("?")[0] if image_url else None

                        items.append(
                            MercariItem(
                                item_id=item_id,
                                title=title.strip(),
                                price=clean_price,
                                price_jpy=jpy,
                                price_usd=usd,
                                currency=currency_text,
                                condition="any",
                                item_url=f"https://jp.mercari.com{href}" if href.startswith("/") else href,
                                description="",
                                source_tier="Mercari PlaywrightScraper Browser",
                                image_url=image_url
                            )
                        )
                    except Exception as item_err:
                        logger.error(f"[Mercari PlaywrightScraper] Error parsing element index {idx}: {item_err}")
                        continue

                await browser.close()
                logger.warning(f"[Mercari PlaywrightScraper] ItemsList generated with: {len(items)}")

        except Exception as e:
            logger.error(f"[Mercari PlaywrightScraper] Execution failed: {e}")
            raise RuntimeError(f"Mercari PlaywrightScraper error: {e}")

        if not items:
            raise ValueError("[Mercari PlaywrightScraper] Zero items retrieved from page DOM.")

        return items

    # New improved way to get both USD and JPY price values
    # Mercari actually includes both usd and jpy prices in its div[aria-label] DOM 
    # So we try to run regex to extract it otherwise use our old method as fallback
    def _extract_price(self, aria_label: str) -> Tuple[str, float, Optional[float], Optional[float]]:
        """
        Parses JPY price, and USD price from thumbnail aria-label string.
        Returns (currency, price_raw, price_jpy, price_usd)
        Example aria-label: "SEIKO 5 自動巻き腕時計の画像 13,800円 US$88.32"
        """
        if not aria_label:
            return "", 0, 0, 0

        # 1. Extract JPY Price
        jpy_price = 0
        jpy_match = re.search(r"([\d,]+)\s*円", aria_label)
        if jpy_match:
            jpy_price = float(jpy_match.group(1).replace(",", ""))

        # 2. Extract USD Price
        usd_price = 0
        usd_match = re.search(r"US\$\s*([\d,.]+)", aria_label)
        if usd_match:
            try:
                usd_price = float(usd_match.group(1).replace(",", ""))
            except ValueError:
                usd_price = 0

        # We will prefer JPY as main currency unless not available
        currency = None
        raw_price = 0
        if jpy_price > 0:
            currency = "JPY"
            raw_price = jpy_price
        elif usd_price > 0:
            currency = "USD"
            raw_price = usd_price

        return currency, raw_price, jpy_price, usd_price


    # Our old way of extracting raw price value, detecting currency and getting usd/jpy price values
    async def _extract_price_fallback(self, el) -> Tuple[str, float, Optional[float], Optional[float]]:
        """
        Fallback method to extract Price and Currency by DOM querying class*='number' and class*='currency'.
        Returns (currency, price_raw, price_jpy, price_usd)
        """
        price_el = await el.query_selector("[class*='number'], [data-testid='price']")
        currency_el = await el.query_selector("[class*='currency'], [data-testid='currency']")

        price_text = await price_el.inner_text() if price_el else "0"
        currency_text = await currency_el.inner_text() if currency_el else None

        # This approach only gets digits and removes decimals, good for JPY but bad if price is USD
        #clean_price = int("".join(filter(str.isdigit, price_text)) or 0)
        # Use a proper regex approach so decimals and commas are preserved
        # !TODO: It is worth exploring that perhaps using price_text (raw value) is better than using 0 or wrong value
        clean_price = float(re.sub(r'[^\d.,]', '', price_text) or 0)

        # We check if currency text has US, $ or US$ and assign the price to price_usd
        # Otherwise its in JPY so store in price_jpy
        usd=0
        jpy=0
        if currency_text:
            if f"US".casefold() in currency_text.casefold() or f"$" in currency_text.casefold():
                usd = clean_price
            else:
                jpy = clean_price
        else:
            jpy = clean_price

        return currency_text, clean_price, jpy, usd