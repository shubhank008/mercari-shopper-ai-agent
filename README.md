# Mercari Japan AI Shopping Assistant — Agent Harness Engine
A production-grade, autonomous **AI Agent Harness** built from scratch in Python.   
Interprets natural language shopping requests, extracts search keyword and constraints , searches Mercari Japan via resilient multi-tier scrapers with fallback, and executes multi-turn tool chaining   
(broad search retrieval + RAG / Deep Enrichment with in-depth product details) to generate reasoned **Top 3 Product Recommendations**.

### Core Engineering Highlights:
* **Zero Third-Party AI Frameworks**: Built strictly without LangChain, LangGraph, or LlamaIndex. All state loops, tool-dispatch registries, context sanitization, and provider failover logic are coded natively in typed, asynchronous Python.
* **Two-Stage Retrieval & Non-Destructive Model Hydration**:
  * *Stage 1 (`search_mercari`)*: Executes sub-second broad search queries returning high-level summary cards.
  * *Stage 2 (`get_item_details`)*: Deeply enriches cherry-picked candidate listing IDs with full in-depth product details including seller ratings, likes, description, condition, etc..
  * *Non-Destructive Delta Patching*: Updates in-memory `MercariItem` Pydantic models in-place, preserving model integrity if detail endpoints time out.
* **Multi-Tier Resilient Scraping Architecture**:
  * **Tier 1 (Direct REST API with DDoP signing)**: Direct JSON payload fetcher (`httpx`) bypassing Next.js App Router client-side rendering limits. Average execution: **~350 ms**.
  * **Tier 2 (Mercapi)**: Fallback wrapper managing dynamic DPoP/JWT cryptographic request signing.
  * **Tier 3 (Playwright Headless Chromium)**: Renders client-side React DOM when static requests are blocked or rate-limited.
* **Dual-LLM Provider Failover**: Primary execution via **Anthropic Claude** model with automatic failover to **OpenAI** model on rate limits (HTTP 429), server errors (HTTP 5xx), or network timeouts.
* **Security Guardrails & Context Optimization**:
  * **PromptGuardrail**: Scans incoming prompts against malicious jailbreak and prompt override regex patterns prior to LLM processing.
  * **ContextSanitizer**: Strips raw HTML and truncates text descriptions, reducing context window bloat and token costs by ~75%.
 

<img height="1000" alt="chrome_h0gfHxKnfT" src="https://github.com/user-attachments/assets/0218eb6c-a19f-4d82-8ab9-03e375685c2c" />
<img height="1000" alt="chrome_wcUUVUoP1u" src="https://github.com/user-attachments/assets/bfc4ec15-7be8-43e4-9aae-8c8717a1cb6e" />




# 1. Setup

## Prerequisites
- Python 3.10 or higher
- python-pip
- (Optional) Playwright browser binaries (For Tier 3 browser fallback)

## Installation

1. Clone the repository
2. Install required dependencies:  
```
pip install -r requirements.txt
```
3. Configure environment variables:  
```
cp .env.example .env
```
4. Add your API keys to `.env` and configure other variables:
```
ANTHROPIC_API_KEY=your_claude_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

#### Playright Installation (Optional)
```
# First install dependencies
playwright install-deps

# Then browser finaries
playwright install
```

## LLM provider selection

Select the primary provider with `LLM_PRIMARY_PROVIDER`. Supported values are `anthropic`, `openai`, and `opencodego`. Configure the matching API key and model ID in `.env`:

```bash
# OpenCode Go uses its OpenAI-compatible chat-completions API.
LLM_PRIMARY_PROVIDER=opencodego
OPENCODEGO_API_KEY=your_opencode_go_api_key_here
OPENCODEGO_MODEL_ID=glm-5.3-flash
OPENCODEGO_BASE_URL=https://opencode.ai/zen/go/v1
```

`glm-5.3-flash` is the default OpenCode Go model because it is documented for the compatible `/chat/completions` endpoint. Other models available on that endpoint can be selected with `OPENCODEGO_MODEL_ID`. The adapter sends an opaque session header per harness instance, as required by OpenCode Go for routing and prompt caching. Do not log or share this session identifier.

Set `ENABLE_LLM_FALLBACK=false` to use only the selected primary provider. When fallback is enabled, the selected provider runs first, followed by any configured providers in deterministic Anthropic, OpenAI, OpenCode Go order.


# 2. Usage Instructions & Logging Modes
## Interactive UI Mode (Clean Terminal UI)  
By default, internal HTTP request logs and execution turn logs are suppressed (LOG_LEVEL=WARNING) to present a clean, formatted terminal UI with animated spinners, tables, and Markdown rendering:
```
python main.py
```
## Single Query Mode  
Run a single natural language shopping query:
```
python main.py --query "Find a vintage Seiko 5 watch under 25000 yen in good condition"
```
## Verbose Execution Mode
To inspect live tool-calling state turns, multi-tier fallback events, HTTP status codes, and turn-by-turn token/cost metrics, set `LOG_LEVEL=INFO` in `.env`.

## Web demo
The browser demo uses the same `AgentHarness` as the CLI. It starts a new in-memory session on every page load, so reloading the page clears its conversation context. Final recommendations include typed Mercari product cards with all available listing images, source metadata, and links that open Mercari in a new tab.

Run it locally after installing dependencies and configuring `.env`:

```bash
python -m uvicorn src.web.app:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The health endpoint is available at `/health` for deployment checks.

# 3. Deployment

All deployments require the same environment variables as the CLI. Set `ANTHROPIC_API_KEY` for normal operation. Set `OPENAI_API_KEY` only when using the optional fallback provider. Never commit `.env` files or provider keys.

## Docker

Build and run the web demo locally:

```bash
docker build -t mercari-shopper .
docker run --rm -p 8000:8000 --env-file .env mercari-shopper
```

The container listens on `$PORT` and defaults to `8000`. Docker deployment uses the included `Dockerfile` and starts `uvicorn src.web.app:app`.

## Railway

1. Create a new Railway project from this repository.
2. Add `ANTHROPIC_API_KEY` and any optional configuration variables in Railway's Variables page.
3. Deploy. Railway reads `railway.toml`, starts the shared ASGI application, and checks `/health`.

## Vercel

1. Import this repository into Vercel.
2. Add `ANTHROPIC_API_KEY` and any optional configuration variables in Project Settings, Environment Variables.
3. Deploy. `vercel.json` routes requests to `api/index.py`, which exports the same ASGI app.

Vercel serverless functions have an execution time limit and in-memory sessions are instance-local. The demo therefore starts a fresh page-scoped session by design and is best suited for interactive evaluation rather than persistent shopping conversations.


# 4. Performance Benchmarks

Measured across production test runs (`MacBook Pro 13 M1`, `iPhone 13 Pro`, `Seiko 5`, `limit=25`):

| Scraper Tier | Implementation | Latency | Reliability Rate |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Primary)** | Custom Direct API | **~350 ms – 470 ms** | 99.8% |
| **Tier 2 (Secondary)** | Mercapi DPoP | **~670 ms** | 98.5% |
| **Tier 3 (Tertiary)** | Playwright Headless Chrome | **~7,200 ms – 9,800 ms** | 95.0% |




# 4. Demo Case Study: Autonomous Self-Correction Trace

When tested with a tricky query - **`find me iphone 13 pro with only new condition`** - the Agent Harness demonstrated **autonomous query refinement** and **multi-turn self-correction**:

### Trace Breakdown:
1. **Turn 1 (`search_mercari`)**: The agent initially searched for `iPhone 13 Pro`, `condition: new`. The scraper returned 25 items, but because accessories are frequently listed as "New", cheap phone cases (¥450–¥1,000) filled the initial results.
2. **Turn 2 (Autonomous Query Refinement)**: Reading the initial search summaries in context, the LLM recognized that accessories dominated the output. Without human intervention, it **self-corrected its search strategy** and executed a second query: `search_mercari(keyword='iPhone 13 Pro 本体 新品未使用', condition='new')` (adding **本体** [handset] and **新品未使用** [brand new unused]).
3. **Turn 3 (`get_item_details`)**: The refined search successfully retrieved actual iPhone handsets. The agent selected candidate IDs (`m59939422043`, `m76698791832`, etc.) and executed `get_item_details` to inspect full seller rating histories and AppleCare exchange notes.
4. **Turn 4 (Synthesis)**: The agent compiled a top 3 handset recommendation list (¥79,000–¥85,000) while completely filtering out the ¥500 cases!


### Execution Log Snippet:
```text
[INFO] Mercari Agent Harness Loop - Turn 1/5
[INFO] Attempting tool call with LLM Provider: Anthropic Claude (claude-sonnet-4-6)
[INFO] [Harness] Agent executing tool: 'search_mercari' with args: {'keyword': 'iPhone 13 Pro', 'condition': 'new'}
[Mercari WebScraper] Searching Mercari JP for keyword: 'iPhone 13 Pro'
[INFO] Search successfully completed using Tier 1 (MercariWebSearchTool). Retrieved 25 items.

[INFO] Mercari Agent Harness Loop - Turn 2/5
[INFO] [Harness] Agent executing tool: 'search_mercari' with args: {'keyword': 'iPhone 13 Pro 本体 新品未使用', 'condition': 'new'}
[INFO] [Mercari WebScraper] Searching Mercari JP for keyword: 'iPhone 13 Pro 本体 新品未使用'
[INFO] Search successfully completed using Tier 1 (MercariWebSearchTool). Retrieved 25 items.

[INFO] Mercari Agent Harness Loop - Turn 3/5
[INFO] [Harness] Agent executing tool: 'get_item_details' with args: {'item_ids': ['m59939422043', 'm76698791832', 'm96533068171', 'm20457581389', 'm52401210011', 'm29852696506']}
[INFO] [Mercari WebScraper] Fetching details for item_id: 'm59939422043'
.
[INFO] [Mercari WebScraper] Fetching details for item_id: 'm29852696506'


[INFO] Mercari Agent Harness Loop - Turn 4/5
[INFO] Anthropic Claude (claude-sonnet-4-6) returned text without requesting tool calls. State loop completed, RETURNING RESULTS.

```


# 5. Design Architecture
## High Level
User Prompt (Natural Language) **-->** LLM Provider + Tool Call (search_mercari) **-->** RAG (get_item_details) **-->** Detailed Result Injection (LLM) **-->** Reasoned Recommendation (JSON) **-->** Output (User Friendly/Natural Language)
## Low Level
- **LLM Provider Call**  
Decoupled-Interface design to add one or more LLM providers for quick switch and scale. Also adds priority-fallback if one provider is down or not available.
- **Tool Call (search_mercari)**  
Multiple scraping mechanisms for a similar fallback approach if one scraper fails. Priority order based on execution time and third-party library usage.
- **RAG / Deep Enrichment**  
Minimal product details are available from initial search for X number of products, so we run them through LLM once to cherry-pick top Y number of products for which we get detailed product data through `get_item_details` and again feed it to the LLM for analysis, reasoning, comparision and give us final output to get our Top 3 product recommendations  
**See detailed explanation below**
- **Guardrails**  
Safety mecanisms against Prompt Injection, garbage output and content trimming - truncate too large descriptions or summarize them to avoid token bloat and usage-costs.

## RAG / Deep Enrichment
Since we limit our `search_mercari` results to X limits, and just general product meta-data (title, price) available from the search results is not enough for deep-analysis and comparision between product choices, we need detailed product meta-data from individual item-pages. 
Yet at same time, we cannot fetch and use detailed product data for all X results because:
- **Latency and Rate Limits:** It will increase overall Agent response latency and run us into Rate Limits by Mercari, potential server/ip blacklist if considered spam requests. (Fetching 25 product details at 2s per product adds 25 requests and 50s latency).
- **Context Window and Cost:** Passing full product details for X results will increase context window size, token usage per search and ultimately resulting in higher per-query cost. It adds more latency for LLM response too.  
So we introduce RAG to our pipeline by initially fetching X number of products through Broad Search, these have minimal details available (title, price).
We feed this broad search results to our Agent/LLM to pick top Y candidates for deeper inspection.  
We run these Y number of products to fetch detailed product data through individual product page scraping to get detailed meta-data (title, price, description, condition, listing date, seller rating, etc.).
The Agent/LLM is fed these detailed results to present its reasoning and selecting our Top 3 recommendations.  
`Example: Broad search can fetch 50 products, Agent first pass picks us 10 products to do deep inspection, out of which 3 top recommendations are made`

## Key Design Choices
1. **Typed State Machine Loop:** The Harness manages tool invocation turns using an explicit loop. Base cases evaluate tool request presence, allowing the agent to perform multi-stage retrieval autonomously without hardcoded execution paths.

2. **In-Memory Delta Model Hydration:** The Harness maintains a session map (`session_items_map: Dict[str, MercariItem]`).  
Stage 1 inserts base listing summaries; Stage 2 patches detailed fields (`description, seller_rating`) in-place via non-destructive delta patching, preserving model integrity even if detail endpoints fail.

3. **Soft Dependency Isolation:** `MercariSearchManager` uses dynamic lazy imports. If playwright or mercapi packages are absent from the environment, the manager skips registration gracefully without crashing.

4. **Context Budgeting:** Mercari search returns large raw DOM payloads. The Harness strips unnecessary fields, converts prices to standard integer JPY, and truncates long descriptions to keep the LLM context window small and responsive.


# 6. Future Improvements
- Production Session Persistence (Experimental): Extend session state with Redis or PostgreSQL backends for persistent conversation memory across restarts.
- Test suites to automate regular testing of LLM Provider uptime (API calls, active key, token/balance availability)
- Test suites to automate regular testing of Mercari Backend (each scraper mecanism working, incase of errors create automated reports or tickets/issues)
- Token, API calls, Backend usage metadata and monitoring to get a overview of how our system is working in terms of speed, usage and cost
- Summary sub-module for large product descriptions instead of truncating it
- Additional Search Backends like Yahoo Auctions, Yahoo PayPay, Sofmap (Used)
- Current-code improvements marked with `!TODO` inline comment (easy-search)
- Add Language Translation (JP->Eng) and currency selector (show price in USD or JPY)
- For Production, final or all Exceptions should be handled into Consumer facing Graceful messages, while internally alerting / logging DevOps

# 7. External Libraries
- **Official LLM SDKs**  
```
anthropic
openai
```

- **Data Models**
```
pydantic
pydantic-settings
python-dotenv
```

- **Web Scraping / API Requests / Key Signing**
```
httpx<0.28.0
beautifulsoup4>=4.12.3

ecdsa>=0.19.0
# Python-Jose required for DDoP-JWT key signing
# https://github.com/mpdavis/python-jose
python-jose[cryptography]
```
- **UI & Utilities**
```
rich
tenacity
```

- **(Optional) For Mercari Fallback Scrapers**  
```
playwright
# https://github.com/take-kun/mercapi
mercapi
```
