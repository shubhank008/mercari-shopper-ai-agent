"""
Fallback Scraper: Playwright Headless Browser Scraper.
Waits for Next.js App Router client-side hydration to render product grid cells.
"""

import logging
import re
from typing import List, Optional
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
                        
                        # Extract price text inside thumbnail
                        price_el = await el.query_selector("[class*='number'], [data-testid='price']")
                        price_text = await price_el.inner_text() if price_el else "0"
                        # This approach only gets digits and removes decimals, good for JPY but bad if price is USD
                        #clean_price = int("".join(filter(str.isdigit, price_text)) or 0)
                        # Use a proper regex approach so decimals and commas are preserved
                        # !TODO: It is worth exploring that perhaps using price_text (raw value) is better than using 0 or wrong value
                        clean_price = float(re.sub(r'[^\d.,]', '', price_text) or 0)

                        # Extract currency
                        currency_el = await el.query_selector("[class*='currency'], [data-testid='currency']")
                        currency_text = await currency_el.inner_text() if currency_el else None

                        usd = 0
                        jpy = 0

                        # We check if currency text has US, $ or US$ and assign the price to price_usd
                        # Otherwise its in JPY so store in price_jpy
                        if currency_text:
                            if f"US".casefold() in currency_text.casefold() or f"$" in currency_text.casefold():
                                usd = clean_price
                            else:
                                jpy = clean_price
                        else:
                            jpy = clean_price

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