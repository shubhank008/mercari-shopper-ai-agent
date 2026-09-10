# Web demo and portable deployment

## Goal

Provide a browser-based demonstration of the Mercari AI Shopper Agent Harness that behaves like the interactive CLI while making recommendations easier to inspect visually.

## User experience

1. A visitor opens a single chat page and sees a short explanation plus suggested shopping prompts.
2. The visitor submits a shopping request and receives the harness's final recommendation as a chat response.
3. The final response includes the existing recommendation text, provider and execution metadata, plus up to three visual product cards selected from the retrieved Mercari listings.
4. Each product card shows every image returned for that listing when available, followed by the title, price, condition, seller rating, likes, source tier, and a Mercari link.
5. Mercari links open in a separate tab and use `rel="noopener noreferrer"`.
6. A browser session retains the conversational context for follow-up requests. Reloading the page creates a new browser session and clears server-side context associated with the previous session.
7. The UI presents recoverable errors as an assistant message and keeps the composer usable.

## Runtime contract

- `GET /` serves the web demo.
- `POST /api/chat` accepts a session identifier and non-empty message, invokes the existing `AgentHarness`, and returns recommendation text, selected product cards, and safe execution metadata.
- No API key, raw scraper response, session cookie, or conversation text is written to the browser, fixture, or application log beyond standard request processing.
- Session state is in-memory only and expires after an idle timeout. It is intentionally unsuitable for multi-instance persistence.

## Deployment targets

The same ASGI application must run through all three documented targets:

- Docker through a production `uvicorn` command.
- Railway through a Nixpacks build and start command.
- Vercel through a Python serverless entry point and route rewrite.

Each target receives the existing provider configuration through environment variables. `ANTHROPIC_API_KEY` is required for normal operation; `OPENAI_API_KEY` remains optional when LLM fallback is enabled.

## Acceptance criteria

- A fresh-page session cannot receive prior-page conversation context.
- A successful response returns a recommendation, metadata, and at most three recommendation cards.
- Cards preserve all available unique image URLs and provide a functioning external Mercari link.
- The rendered link includes a new-tab target and safe `rel` value.
- Invalid chat requests produce client-safe validation errors.
- Docker, Railway, and Vercel configuration files point at the same application.
- README contains setup and deployment instructions for all three targets.

## Non-goals

- Persistent user accounts, database-backed chat history, streaming tokens, authentication, and multi-instance session sharing.
- Automated bypassing of Mercari access challenges.
- Changing the CLI's interaction model or LLM recommendation prompt format.
