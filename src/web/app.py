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


def _fallback_reasoning(item: MercariItem) -> str:
    """Explain a fallback pick using only factual listing fields."""
    price = f"¥{item.price_jpy:,.0f}" if item.price_jpy is not None else "an unavailable price"
    condition = item.condition or "an unavailable condition"
    seller = item.seller_rating_score
    seller_text = f" Seller rating is {seller}/5." if seller is not None else " Seller rating is not available."
    return f"This listing is included for comparison at {price} in {condition} condition.{seller_text} Review the full listing before purchase."


def _fallback_conclusion(products: list[ProductCard]) -> str:
    """Provide a useful final tip when the model omits a conclusion."""
    if not products:
        return "No final purchase recommendation was generated. Review the shortlist and try again."
    return "Compare the top picks against your budget and condition requirements, then verify the listing details, seller history, and item availability before buying."


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
    structured = getattr(harness, "structured_recommendation", None)
    parsed = parse_recommendation(recommendation) if structured is None else None
    if structured is not None:
        logger.info("[WEB_RECOMMENDATION_STRUCTURED] picks=%d", len(structured.picks))
        for pick in structured.picks:
            logger.info("[WEB_RECOMMENDATION_REASONING] rank=%d item_id=%s reasoning=%s", pick.rank, pick.item_id, pick.reasoning)
        logger.info("[WEB_RECOMMENDATION_CONCLUSION] conclusion=%s", structured.conclusion)
    elif parsed.parsed:
        logger.info("[WEB_RECOMMENDATION_PARSED] sections=%d", len(parsed.sections))
    else:
        logger.info("[WEB_RECOMMENDATION_PARSE_FALLBACK]")
    enriched_ids = getattr(harness, "enriched_item_ids", set())
    enriched = [item for item in items if item.item_id in enriched_ids]
    remaining = [item for item in items if item.item_id not in enriched_ids]
    ordered_items = enriched + remaining
    shortlist = [product_card(item) for item in ordered_items]
    products = []
    if structured is not None:
        sections = [RecommendationSection(rank=pick.rank, title=pick.title, reasoning=pick.reasoning) for pick in structured.picks]
        item_by_id = {item.item_id: item for item in ordered_items}
        for pick in sorted(structured.picks, key=lambda value: value.rank):
            item = item_by_id.get(pick.item_id)
            if item is not None:
                products.append(product_card(item, pick.reasoning))
        if len(products) != 3:
            raise HTTPException(status_code=502, detail="The assistant returned recommendations for unavailable listings. Please try again.")
        conclusion = structured.conclusion
        intro = structured.intro
        parsed_flag = True
    else:
        sections = [RecommendationSection.model_validate(section.__dict__) for section in parsed.sections]
        for index, item in enumerate(ordered_items[:3]):
            section = next((candidate for candidate in parsed.sections if candidate.rank == index + 1), None)
            reasoning = section.reasoning if section and section.reasoning else _fallback_reasoning(item)
            if not section:
                sections.append(RecommendationSection(rank=index + 1, title=f"Shortlisted match {index + 1}", reasoning=reasoning))
            products.append(product_card(item, reasoning))
        conclusion = parsed.conclusion or _fallback_conclusion(products)
        intro = parsed.intro or "I compared the available listings and selected the strongest matches for your request."
        parsed_flag = parsed.parsed
    logger.info("[WEB_RECOMMENDATION_RENDERED] shortlist=%d top_picks=%d", len(shortlist), len(products))
    return ChatResponse(
        recommendation=recommendation,
        recommendation_intro=intro,
        recommendation_sections=sections,
        recommendation_conclusion=conclusion,
        recommendation_parsed=parsed_flag,
        shortlist=shortlist,
        products=products,
    )
