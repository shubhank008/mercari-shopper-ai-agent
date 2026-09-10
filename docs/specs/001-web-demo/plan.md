# Implementation plan

## Global constraints

- Keep API keys, raw scraper responses, session state, and browser credentials out of logs, fixtures, and committed artifacts.
- Preserve the existing AgentHarness as the business-logic boundary. The web layer adapts it and does not call Mercari or LLM providers directly.
- Update `.env.example` whenever runtime configuration changes.
- Use focused semantic commits and run the available quality checks before publishing.
- Treat Mercari challenge pages as a failure condition. Do not add challenge-solving behavior.

## Decisions

- Use FastAPI and Jinja templates because FastAPI and Uvicorn are already installed in the environment and match the project's Python runtime.
- Serve a dependency-free HTML, CSS, and JavaScript interface so Docker, Railway, and Vercel share one backend artifact.
- Allocate one `AgentHarness` per opaque browser session identifier. A page reload generates a new identifier, which intentionally provides an empty session.
- Return product cards from retrieved listings rather than parsing the LLM's prose. This prevents fabricated links and lets the UI retain exact source metadata.
- The existing listing model supports one `image_url`. Extend it with `image_urls`, retaining `image_url` for existing consumers and populating both from scraper data.

## Steps

1. Add validated web-session and response schemas plus an image URL normalizer.
2. Adapt Mercari scraper output to retain all listing thumbnails.
3. Build an ASGI web application with per-session harness ownership, bounded in-memory session eviction, client-safe errors, and a thin HTTP adapter.
4. Add a chat page and application assets. Ensure every page load generates a new client session and external item URLs use safe new-tab behavior.
5. Add behavior-driven tests for the API adapter, browser-session reset contract, image payloads, and rendered anchor contract.
6. Add Docker, Railway, and Vercel deployment configuration, plus environment documentation.
7. Add an audit report to the README roadmap section, separating feature-blocking remediation from future improvements.
8. Run tests, lint-style compilation checks, application smoke tests, and capture a rendered browser frame.
