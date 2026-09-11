"""ASGI application serving the Mercari AI Shopper browser demo."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from src.config import config
from src.data_models.query import MercariItem
from src.web.models import ChatRequest, ChatResponse, ProductCard, RecommendationSection
from src.web.recommendation_parser import parse_recommendation
from src.web.session_store import HarnessSessionStore

logger = logging.getLogger(__name__)
static_path = Path(__file__).parent / "static"

app = FastAPI(title="Mercari AI Shopper", version="1.0.0")
app.mount("/static", StaticFiles(directory=static_path), name="static")
store = HarnessSessionStore(idle_seconds=config.web_session_idle_seconds)


def product_card(item: MercariItem, reasoning: str = "") -> ProductCard:
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
    parsed = parse_recommendation(recommendation)
    if parsed.parsed:
        logger.info("[WEB_RECOMMENDATION_PARSED] sections=%d", len(parsed.sections))
    else:
        logger.info("[WEB_RECOMMENDATION_PARSE_FALLBACK]")
    enriched_ids = getattr(harness, "enriched_item_ids", set())
    enriched = [item for item in items if item.item_id in enriched_ids]
    remaining = [item for item in items if item.item_id not in enriched_ids]
    ordered_items = enriched + remaining
    sections = [RecommendationSection.model_validate(section.__dict__) for section in parsed.sections]
    shortlist = [product_card(item) for item in ordered_items]
    products = []
    for index, item in enumerate(ordered_items[:3]):
        section = next((candidate for candidate in parsed.sections if candidate.rank == index + 1), None)
        reasoning = section.reasoning if section and section.reasoning else "Selected from the assistant's final shortlist."
        products.append(product_card(item, reasoning))
    logger.info("[WEB_RECOMMENDATION_RENDERED] shortlist=%d top_picks=%d", len(shortlist), len(products))
    return ChatResponse(
        recommendation=recommendation,
        recommendation_intro=parsed.intro,
        recommendation_sections=sections,
        recommendation_conclusion=parsed.conclusion,
        recommendation_parsed=parsed.parsed,
        shortlist=shortlist,
        products=products,
    )
