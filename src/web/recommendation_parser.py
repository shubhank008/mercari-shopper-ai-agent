"""Partition LLM recommendation prose for structured browser presentation."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationSection:
    """A ranked recommendation heading and its reasoned analysis."""

    rank: int
    title: str
    reasoning: str


@dataclass(frozen=True)
class ParsedRecommendation:
    """Presentation-safe sections extracted from recommendation prose."""

    intro: str
    sections: list[RecommendationSection]
    conclusion: str
    parsed: bool


_HEADING = re.compile(
    r"(?im)^\s{0,3}(?:#{1,6}\s*)?(?:\*{0,2}(?:Recommendation|Pick|Option)\s*(?:#?\s*)?)?(\d+)\s*[:.)-]\s*(.+?)\*{0,2}\s*$"
)
_CONCLUSION = re.compile(
    r"(?im)^\s{0,3}(?:#{1,6}\s*)?\*{0,2}(?:Final purchase recommendation|Final recommendation|Purchase recommendation|Final tip|Conclusion|Summary)\s*:??\s*\*{0,2}\s*$"
)
_REASON = re.compile(r"(?im)^\s*\*{0,2}Reasoned Analysis\*{0,2}\s*:\s*\*{0,2}")
_BOLD_LINE = re.compile(r"(?m)^\s*\*{2}(.+?)\*{2}\s*$")
_INLINE_CONCLUSION = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?\*{0,2}(?:Final tip|Final purchase recommendation|Final recommendation|Conclusion|Summary)\*{0,2}\s*:\s*(.+?)\s*$"
)
_FIELD_LABELS = {"price", "condition", "seller rating", "seller", "url", "reasoned analysis"}


def _clean(text: str) -> str:
    """Remove presentation separators while preserving readable paragraph breaks."""
    text = re.sub(r"(?m)^\s*-{3,}\s*$", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_reasoned_blocks(text: str) -> ParsedRecommendation | None:
    """Parse recommendation prose whose ranked headings are product title lines."""
    reason_matches = list(_REASON.finditer(text))
    if not reason_matches:
        return None
    sections: list[RecommendationSection] = []
    first_title_matches = [
        match for match in _BOLD_LINE.finditer(text[: reason_matches[0].start()])
        if match.group(1).split(":", 1)[0].strip().lower() not in _FIELD_LABELS
    ]
    intro = _clean(text[: first_title_matches[-1].start()]) if first_title_matches else ""
    all_title_matches = [
        match for match in _BOLD_LINE.finditer(text)
        if match.group(1).split(":", 1)[0].strip().lower() not in _FIELD_LABELS
    ]
    for index, reason_match in enumerate(reason_matches[:3]):
        title_candidates = [match for match in all_title_matches if match.start() < reason_match.start()]
        title = title_candidates[-1].group(1) if title_candidates else f"Recommendation {index + 1}"
        next_title = next((match for match in all_title_matches if match.start() > reason_match.start()), None)
        end = next_title.start() if next_title else len(text)
        conclusion_match = _CONCLUSION.search(text[reason_match.end() : end])
        body_end = reason_match.end() + conclusion_match.start() if conclusion_match else end
        reasoning = _clean(_REASON.sub("", text[reason_match.end() : body_end], count=1))

        sections.append(RecommendationSection(rank=index + 1, title=_clean(title), reasoning=reasoning))
    conclusion_match = _CONCLUSION.search(text)
    inline_conclusion = _INLINE_CONCLUSION.search(text)
    conclusion = _clean(text[conclusion_match.end() :]) if conclusion_match else (inline_conclusion.group(1).strip() if inline_conclusion else "")
    return ParsedRecommendation(intro=intro, sections=sections, conclusion=conclusion, parsed=True)


def parse_recommendation(text: str) -> ParsedRecommendation:
    """Extract ranked sections without interpreting or rewriting their content."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        fallback = _parse_reasoned_blocks(text)
        if fallback:
            return fallback
        return ParsedRecommendation(intro="", sections=[], conclusion=_clean(text), parsed=False)

    intro = _clean(text[: matches[0].start()])
    sections: list[RecommendationSection] = []
    conclusion = ""
    for index, match in enumerate(matches):
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : body_end]
        conclusion_match = _CONCLUSION.search(body)
        if conclusion_match:
            reasoning = _clean(body[: conclusion_match.start()])
            conclusion = _clean(body[conclusion_match.end() :])
        else:
            inline_conclusion = _INLINE_CONCLUSION.search(body)
            if inline_conclusion:
                reasoning = _clean(body[: inline_conclusion.start()])
                conclusion = inline_conclusion.group(1).strip()
            else:
                reasoning = _clean(body)
            reasoning = _clean(_REASON.sub("", reasoning, count=1))
        sections.append(
            RecommendationSection(
                rank=int(match.group(1)),
                title=_clean(match.group(2)),
                reasoning=reasoning,
            )
        )
    return ParsedRecommendation(intro=intro, sections=sections, conclusion=conclusion, parsed=True)
