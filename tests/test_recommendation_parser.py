"""Tests for structured recommendation prose partitioning."""

import unittest

from src.web.recommendation_parser import parse_recommendation


class RecommendationParserTests(unittest.TestCase):
    """Verify ranked reasoning and final conclusions are separated once."""

    def test_partition_ranked_sections_and_conclusion(self) -> None:
        """Extract intro, three ranked bodies, and the final purchase tip."""
        text = """Based on the detailed listings, here are my top 3 recommendations.\n\n---\n\n## Recommendation 1: Best Overall Value\n\n**Reasoned Analysis:** Best value because of coverage.\n\n## Recommendation 2: Best Battery\n\n**Reasoned Analysis:** Strong battery health.\n\n## Recommendation 3: Lowest Price\n\n**Reasoned Analysis:** Cheapest acceptable option.\n\n## Final Purchase Recommendation\n\nChoose Recommendation 1 for the best balance."""
        parsed = parse_recommendation(text)
        self.assertTrue(parsed.parsed)
        self.assertIn("top 3", parsed.intro)
        self.assertEqual([section.rank for section in parsed.sections], [1, 2, 3])
        self.assertIn("Best value", parsed.sections[0].reasoning)
        self.assertIn("Choose Recommendation 1", parsed.conclusion)
        self.assertNotIn("Final Purchase", parsed.sections[-1].reasoning)

    def test_bold_product_titles_and_reason_labels_are_partitioned(self) -> None:
        """Parse the compact markdown format returned by the live OpenCode Go run."""
        text = """Based on my analysis, here are the top 3 recommendations.\n\n**Phone A**\n- **Price:** ¥138,900\n\n**Reasoned Analysis:** Best value with coverage.\n\n**Phone B**\n- **Price:** ¥140,000\n\n**Reasoned Analysis:** Highest battery health.\n\n**Phone C**\n- **Price:** ¥117,800\n\n**Reasoned Analysis:** Lowest trustworthy price.\n\n## Final Purchase Recommendation\n\nChoose Phone A."""
        parsed = parse_recommendation(text)
        self.assertTrue(parsed.parsed)
        self.assertEqual([section.title for section in parsed.sections], ["Phone A", "Phone B", "Phone C"])
        self.assertEqual(parsed.sections[0].reasoning, "Best value with coverage.")
        self.assertEqual(parsed.sections[1].reasoning, "Highest battery health.")
        self.assertEqual(parsed.conclusion, "Choose Phone A.")

    def test_numbered_markdown_headings_are_ranked_sections(self) -> None:
        """Parse OpenCode Go's numbered markdown recommendation headings."""
        text = """## Top Recommendations\n\n### 1. Best value\nFirst analysis.\n\n### 2. Best battery\nSecond analysis.\n\n### 3. Lowest price\nThird analysis.\n\nFinal tip: choose the first."""
        parsed = parse_recommendation(text)
        self.assertTrue(parsed.parsed)
        self.assertEqual([section.rank for section in parsed.sections], [1, 2, 3])
        self.assertEqual(parsed.sections[1].title, "Best battery")

    def test_unstructured_text_uses_single_fallback(self) -> None:
        """Keep unexpected prose intact without duplicating it into cards."""
        parsed = parse_recommendation("A short recommendation without ranked headings.")
        self.assertFalse(parsed.parsed)
        self.assertEqual(parsed.sections, [])
        self.assertEqual(parsed.conclusion, "A short recommendation without ranked headings.")


if __name__ == "__main__":
    unittest.main()
