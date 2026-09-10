# Rich recommendation presentation marker contract

| Marker | Meaning |
|---|---|
| `[WEB_RECOMMENDATION_RENDERED]` | A response included the shortlist and final recommendation presentation. |
| `[WEB_IMAGE_LIGHTBOX_OPENED]` | The browser opened a product image in the enlarged viewer. |

The public response and browser result must not expose:

- Provider names
- Scraper tier names
- Request latency or turn counts
- Raw provider payloads
- API keys or session headers
