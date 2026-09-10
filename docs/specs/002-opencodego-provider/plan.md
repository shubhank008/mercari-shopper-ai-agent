# Implementation plan

## Global constraints

- Keep API keys and opaque session IDs out of logs, responses, fixtures, and commits.
- Preserve `BaseLLMProvider` as the integration boundary. The harness must not call OpenCode Go directly.
- Reuse the OpenAI Python SDK compatible `base_url` support rather than adding an HTTP client dependency.
- Update `.env.example` with every accepted runtime key.
- Use deterministic tests with injected clients. Do not call the provider's production endpoint.

## Steps

1. Add explicit primary-provider and OpenCode Go configuration fields with selection validation.
2. Add an OpenAI-compatible OpenCode Go provider adapter with a stable opaque session header and shared tool serialization.
3. Refactor the manager to build configured providers in primary-first deterministic fallback order.
4. Add tests for request construction, tool parsing, configuration validation, and provider ordering.
5. Document configuration and provider limitations in README.
