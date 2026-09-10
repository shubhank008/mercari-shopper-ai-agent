# Web demo marker contract

The web runtime emits structured application log messages containing these markers:

| Marker | Meaning |
|---|---|
| `[WEB_SESSION_CREATED]` | A new in-memory harness session was created. |
| `[WEB_CHAT_COMPLETED]` | A harness request completed and a response was returned. |
| `[WEB_CHAT_REJECTED]` | The request failed input validation or a guardrail check. |
| `[WEB_CHAT_FAILED]` | The harness raised an unexpected exception and the user received a safe error. |

The following patterns must not appear in application logs or response payloads:

- API key values
- Raw `Authorization`, `DPoP`, cookie, or session headers
- Raw Mercari response bodies
- Python stack traces in client responses
