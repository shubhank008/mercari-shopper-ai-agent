"""Tests for the fixed structured recommendation contract."""

import unittest

from pydantic import ValidationError

from src.data_models.recommendation import StructuredRecommendation


class StructuredRecommendationTests(unittest.TestCase):
    """Ensure structured provider output is complete and item-linked."""

    def test_accepts_exactly_three_distinct_ranked_picks(self) -> None:
        """Validate the contract required by CLI and web presentation."""
        result = StructuredRecommendation.model_validate({
            "intro": "I compared the listings.",
            "picks": [
                {"rank": 1, "item_id": "m1", "title": "One", "reasoning": "Best value."},
                {"rank": 2, "item_id": "m2", "title": "Two", "reasoning": "Best condition."},
                {"rank": 3, "item_id": "m3", "title": "Three", "reasoning": "Lowest cost."},
            ],
            "conclusion": "Choose the first after checking the listing.",
        })
        self.assertEqual([pick.item_id for pick in result.picks], ["m1", "m2", "m3"])

    def test_rejects_duplicate_item_ids(self) -> None:
        """Prevent one model listing from receiving multiple recommendation ranks."""
        with self.assertRaises(ValidationError):
            StructuredRecommendation.model_validate({
                "intro": "Compare these.",
                "picks": [
                    {"rank": 1, "item_id": "m1", "title": "One", "reasoning": "A."},
                    {"rank": 2, "item_id": "m1", "title": "One", "reasoning": "B."},
                    {"rank": 3, "item_id": "m3", "title": "Three", "reasoning": "C."},
                ],
                "conclusion": "Check details.",
            })


if __name__ == "__main__":
    unittest.main()
