# Project audit, 2026-07-08

## Scope reviewed

The current CLI entry point, configuration, AgentHarness loop, LLM fallback manager, Mercari direct scraper, listing model, guardrails, test file, dependency list, documentation, and delivery configuration were reviewed after the merged `AGENTS.md` changes were synchronized.

## Findings to address in this feature

1. **No HTTP or deployment boundary exists.** The project is CLI-only, so there is no safe reusable endpoint for a web demo or deploy target. Add a thin ASGI adapter around `AgentHarness`.
2. **The browser has no trustworthy recommendation-card source.** The final answer is unstructured prose, though the harness already returns typed retrieved listings. Return presentation-safe cards from those listings rather than parsing LLM text.
3. **Only a single thumbnail is retained.** The direct scraper discards all but the first thumbnail. Preserve a normalized list of available image URLs while retaining the current primary-image field for compatibility.
4. **Session state has no browser lifecycle boundary.** The CLI stores context in one harness instance. The web adapter must allocate state per opaque page session and make reload create a new session.
5. **No deployment artifacts or documentation exist.** Docker, Railway, Vercel configuration, production start semantics, and environment-variable guidance must accompany the web demo.

## High-priority follow-up improvements

1. **Replace `tests/tests.py` with real test discovery.** It executes live code at import time, includes commented-out ad hoc probes, and has no assertions. Add pytest configuration and deterministic unit and integration tests. The web feature will establish this for HTTP behavior, but scraper and provider contracts still need fixtures.
2. **Pin production dependencies.** `requirements.txt` has broad lower bounds, contrary to the repository invariant. Resolve and deliberately pin a tested Python 3.10+ dependency set in a separate dependency-hardening change.
3. **Remove committed debug logs and runtime writes.** `web_debug.log` and `playwright_debug.log` are tracked, and the direct scraper overwrites `web_debug.log` with raw remote response data. This can leak sensitive or third-party data and causes concurrent request corruption. Replace it with redacted, opt-in diagnostic logging and add logs to `.gitignore`.
4. **Close HTTP clients.** Scraper tools construct `httpx.AsyncClient` instances without a defined close lifecycle. Add an async close contract to backends and call it from an application lifespan handler.
5. **Align configuration documentation.** `.env.example` names current provider models but `AppConfig` defaults still reference older model identifiers. Make models explicit, validate provider keys at startup, and document server-specific fields.

## Medium-priority follow-up improvements

1. Add explicit request timeouts around scraper calls, bounded retries with retry-safe policy, and client-safe exception mapping.
2. Strengthen prompt injection handling beyond six regex patterns. Keep deterministic local guardrails while defining a threat model and tests for untrusted listing content.
3. Validate `get_item_details` hydration data before model updates. `model_copy(update=...)` bypasses Pydantic validators.
4. Fix data-model consistency: price is a float despite JPY integer handling, `currency` defaults to USD, and `listing_date` type/comment mismatch.
5. Add observability around provider fallback, scraper tier selection, request duration, and error classes using redacted structured logs.
6. Update README wording and architecture diagrams, including stale performance figures and descriptions that claim a JSON recommendation although output is prose.

## Deferred scope

Persistent chat history, user authentication, a database, streaming responses, a full observability stack, multi-provider image enrichment, and scraper architectural changes are deliberately deferred so the initial web demo remains small and deployable.
