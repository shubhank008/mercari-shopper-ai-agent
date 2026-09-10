# Configurable OpenCode Go provider

## Goal

Allow an operator to select OpenCode Go as the primary language-model provider through environment configuration and choose its default model without editing application code.

## Configuration contract

- `LLM_PRIMARY_PROVIDER` selects the first provider: `anthropic`, `openai`, or `opencodego`.
- `OPENCODEGO_API_KEY` supplies the OpenCode Go API key when `opencodego` is selected.
- `OPENCODEGO_MODEL_ID` selects the OpenCode Go chat-completions model. Its default is `glm-5.3-flash`.
- `OPENCODEGO_BASE_URL` defaults to `https://opencode.ai/zen/go/v1`.
- Existing providers remain supported. When fallback is enabled, configured providers other than the selected primary provider are attempted after the primary in deterministic Anthropic, OpenAI, OpenCode Go order.

## OpenCode Go API contract

The adapter uses the OpenAI-compatible chat-completions endpoint under the configured base URL. OpenCode Go documents `glm-5.3-flash` at `https://opencode.ai/zen/go/v1/chat/completions` as OpenAI-compatible. Source: https://opencode.ai/docs/go/#endpoints, accessed 2026-07-08.

Each request includes a stable `x-opencode-session` header for one harness conversation, per official guidance. Its opaque value is never logged or returned. Source: https://opencode.ai/docs/go/#where-can-i-use-it, accessed 2026-07-08.

## Acceptance criteria

- Selecting OpenCode Go initializes it before fallbacks.
- The adapter uses the configured model, base URL, timeout, OpenAI-format tools, session header, and an application User-Agent.
- Tool-call parsing and token metrics follow the OpenAI provider contract.
- Invalid provider selection fails configuration validation.
- The template and README document selection and model configuration.

## Non-goals

- Support for OpenCode Go `/responses` or `/messages` models, model discovery, billing, or live-provider automated tests.
