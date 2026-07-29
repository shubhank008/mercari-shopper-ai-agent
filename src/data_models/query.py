"""
Data Models containing Pydantic schemas for User Query parsing,
Mercari product listings, and agent execution logs.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Main class to parse user's natural language query into structured data
class UserQuery(BaseModel):

    keyword: str = Field(
        ...,
        description="Primary item keyword or product title (English or Japanese)."
    )
    min_price: Optional[int] = Field(
        default=None,
        ge=0,
        description="Minimum budget in JPY (¥)."
    )
    max_price: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum budget in JPY (¥)."
    )
    condition: Optional[str] = Field(
        default=None,
        description="Item condition ('new', 'like_new', 'used', 'any')."
    )
    category: Optional[str] = Field(
        default=None,
        description="Product category, if specified."
    )

# Main class to parse Mercari's product listing data
class MercariItem(BaseModel):

    item_id: str = Field(..., description="Unique Mercari item identifier.")
    title: str = Field(..., description="Item listing title.")
    price: int = Field(..., ge=0, description="Listing price in JPY (¥).")
    item_url: str = Field(..., description="Direct URL to item listing page on Mercari JP.")
    # Optional
    condition: str = Field(default="Unknown", description="Item condition description.")
    image_url: Optional[str] = Field(default=None, description="Primary product thumbnail image URL.")
    description: Optional[str] = Field(default="", description="Product description.")
    seller_rating: Optional[str] = Field(default="N/A", description="Seller rating or badge if available.")
    # !TODO: Might need to change listing_date from str to timestamp if want to convert it to natural language (7 days ago)
    listing_date: Optional[str] = Field(default="N/A", description="Seller rating or badge if available.")
    source_tier: str = Field(default="primary", description="Scraper tier that retrieved this item.")
    fetch_time: float = Field(default=0, description="Execution time for this scrape call")

# Individual Agent loop-step log
class AgentStepLog(BaseModel):

    step_number: int
    action: str
    provider_used: str
    details: Dict[str, Any]
    status: str = "SUCCESS"

# Session State tracking, conversation history and execution steps
class AgentState(BaseModel):

    session_id: str
    user_prompt: str
    extracted_query: Optional[UserQuery] = None
    retrieved_items: List[MercariItem] = Field(default_factory=list)
    step_logs: List[AgentStepLog] = Field(default_factory=list)
    active_llm_provider: str = "unknown"
    active_search_tier: str = "unknown"
    is_completed: bool = False