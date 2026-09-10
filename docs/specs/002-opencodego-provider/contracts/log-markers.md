# OpenCode Go provider marker contract

| Marker | Meaning |
|---|---|
| `[OPENCODEGO_PROVIDER_INITIALIZED]` | A configured OpenCode Go adapter was initialized without logging credentials. |
| `[OPENCODEGO_REQUEST]` | A chat-completions request was issued using the selected model. |

The following must never appear in logs or HTTP response payloads:

- `OPENCODEGO_API_KEY` values
- the `Authorization` header value
- the opaque `x-opencode-session` value
- full provider request or response bodies
