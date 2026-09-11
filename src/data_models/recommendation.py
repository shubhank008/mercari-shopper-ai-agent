"""Validated structured recommendation output shared by CLI and web clients."""

from pydantic import BaseModel, Field, model_validator


class RecommendationPick(BaseModel):
    """One ranked recommendation linked to an actual retrieved item ID."""

    rank: int = Field(ge=1, le=3)
    item_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    reasoning: str = Field(min_length=1, max_length=2_000)


class StructuredRecommendation(BaseModel):
    """Complete recommendation contract returned by the final synthesis step."""

    intro: str = Field(min_length=1, max_length=2_000)
    picks: list[RecommendationPick] = Field(min_length=3, max_length=3)
    conclusion: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_unique_ranks(self) -> "StructuredRecommendation":
        """Ensure the three picks have unique ranks and item identifiers."""
        if {pick.rank for pick in self.picks} != {1, 2, 3}:
            raise ValueError("Recommendation ranks must be exactly 1, 2, and 3.")
        if len({pick.item_id for pick in self.picks}) != 3:
            raise ValueError("Recommendation item IDs must be unique.")
        return self
