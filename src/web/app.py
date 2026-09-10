"""ASGI application serving the Mercari AI Shopper browser demo."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from src.config import config
from src.data_models.query import MercariItem
from src.web.models import ChatRequest, ChatResponse, ProductCard
from src.web.session_store import HarnessSessionStore

logger = logging.getLogger(__name__)
static_path = Path(__file__).parent / "static"

app = FastAPI(title="Mercari AI Shopper", version="1.0.0")
app.mount("/static", StaticFiles(directory=static_path), name="static")
store = HarnessSessionStore(idle_seconds=config.web_session_idle_seconds)


def product_card(item: MercariItem, reasoning: str) -> ProductCard:
    """Create a display card while preserving trusted listing and reasoning data."""
    image_urls = list(dict.fromkeys(url for url in [*item.image_urls, item.image_url] if url))
    return ProductCard(
        item_id=item.item_id,
        title=item.title,
        item_url=item.item_url,
        image_urls=image_urls,
        price_jpy=item.price_jpy,
        price_usd=item.price_usd,
        condition=item.condition,
        seller_name=item.seller_name,
        seller_rating_score=item.seller_rating_score,
        seller_total_ratings=item.seller_total_ratings,
        num_likes=item.num_likes,
        reasoning=reasoning,
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the single-page chat interface."""
    return FileResponse(static_path / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    """Provide a deployment-friendly health response without calling providers."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    """Run one browser message through its page-scoped AgentHarness."""
    harness, created = store.get(payload.session_id)
    if created:
        logger.info("[WEB_SESSION_CREATED] session initialized")

    try:
        recommendation, items, provider, tier, metrics = await harness.run(payload.message)
    except ValidationError as exc:
        logger.warning("[WEB_CHAT_REJECTED] harness input validation failed")
        raise HTTPException(status_code=400, detail="Please revise your shopping request.") from exc
    except Exception:
        logger.exception("[WEB_CHAT_FAILED] harness request failed")
        raise HTTPException(
            status_code=502,
            detail="The shopping assistant could not complete that request. Please try again.",
        )

    logger.info("[WEB_CHAT_COMPLETED] recommendation returned")
    enriched_ids = getattr(harness, "enriched_item_ids", set())
    enriched = [item for item in items if item.item_id in enriched_ids]
    remaining = [item for item in items if item.item_id not in enriched_ids]
    ordered_items = enriched + remaining
    shortlist = [product_card(item, recommendation) for item in ordered_items]
    logger.info("[WEB_RECOMMENDATION_RENDERED] shortlist=%d top_picks=%d", len(shortlist), min(3, len(shortlist)))
    return ChatResponse(
        recommendation=recommendation,
        shortlist=shortlist,
        products=shortlist[:3],
    )
