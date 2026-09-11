"""Behavior tests for the browser API adapter and presentation contract."""

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.data_models.query import MercariItem
from src.data_models.recommendation import RecommendationPick, StructuredRecommendation
from src.web import app as web_app


class FakeHarness:
    """Provides deterministic harness behavior through the real HTTP adapter."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def run(self, message: str):
        """Return a response that exposes all recommendation-card data paths."""
        self.messages.append(message)
        item = MercariItem(
            item_id="m123",
            title="Vintage Seiko 5",
            price=18_500,
            price_jpy=18_500,
            item_url="https://jp.mercari.com/item/m123",
            image_url="https://images.example/first.jpg",
            image_urls=[
                "https://images.example/first.jpg",
                "https://images.example/second.jpg",
            ],
            condition="Good",
            seller_name="Trusted seller",
            seller_rating_score=4.9,
            seller_total_ratings=52,
            num_likes=8,
            source_tier="Test search",
        )
        return "This is the best match.", [item], "Test provider", "Test search", {
            "total_duration_ms": 42.0,
            "total_input_tokens": 10,
            "total_output_tokens": 20,
            "total_turns": 2,
        }

class StructuredFakeHarness(FakeHarness):
    """Exposes validated structured reasoning for the API contract test."""

    def __init__(self) -> None:
        super().__init__()
        self.structured_recommendation = StructuredRecommendation(
            intro="I compared the listings.",
            picks=[
                RecommendationPick(rank=1, item_id="m123", title="Best value", reasoning="Best value because of condition."),
                RecommendationPick(rank=2, item_id="m124", title="Best seller", reasoning="Best seller history."),
                RecommendationPick(rank=3, item_id="m125", title="Lowest price", reasoning="Lowest price within the target."),
            ],
            conclusion="Choose the first after checking the listing.",
        )

    async def run(self, message: str):
        """Return three listings matching the structured recommendation IDs."""
        base = await super().run(message)
        first = base[1][0]
        items = [
            first,
            first.model_copy(update={"item_id": "m124", "title": "Trusted seller listing", "item_url": "https://jp.mercari.com/item/m124"}),
            first.model_copy(update={"item_id": "m125", "title": "Lowest price listing", "item_url": "https://jp.mercari.com/item/m125"}),
        ]
        return base[0], items, base[2], base[3], base[4]




class FakeStore:
    """Tracks session IDs while providing a fresh fake harness per browser session."""

    def __init__(self) -> None:
        self.sessions: dict[str, FakeHarness] = {}

    def get(self, session_id: str):
        created = session_id not in self.sessions
        self.sessions.setdefault(session_id, FakeHarness())
        return self.sessions[session_id], created


class WebApplicationTests(unittest.TestCase):
    """Exercise the deployed HTTP interface without LLM or scraper mocks."""

    def setUp(self) -> None:
        self.original_store = web_app.store
        self.store = FakeStore()
        web_app.store = self.store
        self.client = TestClient(web_app.app)

    def tearDown(self) -> None:
        web_app.store = self.original_store

    def test_health_endpoint_reports_ready(self) -> None:
        """Allow deployment platforms to detect a running server."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_returns_images_metadata_and_unique_product_urls(self) -> None:
        """Ensure visual recommendation data comes from typed listing results."""
        response = self.client.post("/api/chat", json={"session_id": "page-one", "message": "Find a watch"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["recommendation"], "This is the best match.")
        self.assertEqual(body["products"][0]["image_urls"], [
            "https://images.example/first.jpg",
            "https://images.example/second.jpg",
        ])
        self.assertEqual(body["products"][0]["item_url"], "https://jp.mercari.com/item/m123")
        self.assertEqual(body["products"][0]["seller_name"], "Trusted seller")
        self.assertIn("reasoning", body["products"][0])
        self.assertEqual(len(body["shortlist"]), 1)
        self.assertNotIn("provider", body)
        self.assertNotIn("search_tier", body)
        self.assertNotIn("source_tier", body["products"][0])
        self.assertFalse(body["recommendation_parsed"])
        self.assertEqual(len(body["recommendation_sections"]), 1)
        self.assertEqual(body["recommendation_sections"][0]["title"], "Shortlisted match 1")
        self.assertEqual(body["recommendation_conclusion"], "This is the best match.")
        self.assertTrue(body["products"][0]["reasoning"])

    def test_new_page_session_uses_a_new_harness(self) -> None:
        """Model page reload behavior by sending an unrelated session identifier."""
        self.client.post("/api/chat", json={"session_id": "before-reload", "message": "First request"})
        self.client.post("/api/chat", json={"session_id": "after-reload", "message": "Second request"})
        self.assertEqual(self.store.sessions["before-reload"].messages, ["First request"])
        self.assertEqual(self.store.sessions["after-reload"].messages, ["Second request"])

    def test_empty_chat_message_is_rejected(self) -> None:
        """Reject blank requests before creating a harness or calling external services."""
        response = self.client.post("/api/chat", json={"session_id": "new-page", "message": "   "})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.store.sessions, {})

    def test_structured_recommendation_preserves_exact_reasoning_and_conclusion(self) -> None:
        """Verify structured provider fields are available without prose parsing."""
        original_store = web_app.store
        store = FakeStore()
        structured = StructuredFakeHarness()
        store.sessions["structured"] = structured
        web_app.store = store
        try:
            response = self.client.post("/api/chat", json={"session_id": "structured", "message": "Find a watch"})
        finally:
            web_app.store = original_store
        body = response.json()
        self.assertEqual(body["recommendation_intro"], "I compared the listings.")
        self.assertEqual(body["recommendation_conclusion"], "Choose the first after checking the listing.")
        self.assertEqual(body["products"][0]["reasoning"], "Best value because of condition.")


    def test_html_declares_safe_external_mercari_link_contract(self) -> None:
        """Serve the browser page with a safe link template for recommendation cards."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('target="_blank" rel="noopener noreferrer"', response.text)
        self.assertIn('id="lightbox"', response.text)
        self.assertIn('class="product-reasoning"', response.text)
        self.assertIn('rows="2"', response.text)
        javascript = (Path(__file__).parent.parent / "src/web/static/app.js").read_text()
        styles = (Path(__file__).parent.parent / "src/web/static/styles.css").read_text()
        self.assertIn('className = "recommendation-conclusion"', javascript)
        self.assertIn('className = "pick-heading"', javascript)
        self.assertIn('height: auto', styles)


if __name__ == "__main__":
    unittest.main()
