"""Typed request and presentation models for the browser demo."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """A browser message associated with an opaque, page-scoped session."""

    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4_000)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        """Reject whitespace-only requests before invoking the harness."""
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty.")
        return value


class ProductCard(BaseModel):
    """Safe presentation data derived from a trusted Mercari listing."""

    item_id: str
    title: str
    item_url: str
    image_urls: list[str] = Field(default_factory=list)
    price_jpy: Optional[float] = None
    price_usd: Optional[float] = None
    condition: str
    seller_name: Optional[str] = None
    seller_rating_score: Optional[float] = None
    seller_total_ratings: Optional[int] = None
    num_likes: Optional[int] = None
    reasoning: str = "Included in the assistant's shortlisted results for this request."


class ChatResponse(BaseModel):
    """The recommendation prose, complete shortlist, and visual top picks."""

    recommendation: str
    shortlist: list[ProductCard] = Field(default_factory=list)
    products: list[ProductCard] = Field(default_factory=list)
