"""Behavior tests for the browser API adapter and presentation contract."""

import unittest

from fastapi.testclient import TestClient

from src.data_models.query import MercariItem
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
        self.assertEqual(body["metrics"]["total_turns"], 2)

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

    def test_html_declares_safe_external_mercari_link_contract(self) -> None:
        """Serve the browser page with a safe link template for recommendation cards."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('target="_blank" rel="noopener noreferrer"', response.text)


if __name__ == "__main__":
    unittest.main()
