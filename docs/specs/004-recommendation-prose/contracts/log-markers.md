# Recommendation prose marker contract

| Marker | Meaning |
|---|---|
| `[WEB_RECOMMENDATION_PARSED]` | The response prose was partitioned into intro, ranked sections, and conclusion. |
| `[WEB_RECOMMENDATION_PARSE_FALLBACK]` | The response did not match the ranked format and was rendered once as fallback prose. |

The browser must not:

- repeat the complete recommendation text in every product card
- distort product image aspect ratios
- omit a conclusion that exists in the LLM response
