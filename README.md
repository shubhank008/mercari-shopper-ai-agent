# mercari-shopper-ai-agent
AI-Agent harness for shopping on Mercari Japan

# Overview
AI Agent to search and recommend products from Mercari (JP) using user's NaturalLanguage prompt.

# Demo

# Setup

## Playright Installation
Initial setup by running `playwright install-deps` and `playwright install` to install the browsers

## Mercarpi Installation

# Usage

# Design Architecture
## High Level
User Prompt (Natural Language)-> LLM Provider call + Tool Call (search_mercari)-> RAG (get_item_details)-> Result Injection (LLM)-> Reasoned Recommendation (JSON)-> Output (User Friendly/Natural Language)
## Low Level
- LLM Provider Call
Decoupled-Interface design to add one or more LLM providers for quick switch and scale. Also adds priority-fallback if one provider is down or not available.
- Tool Call (search_mercari)
Multiple scraping mechanisms for a similar fallback approach if one scraper fails. Priority order based on execution time and third-party library usage.
- RAG
Fetch minimal product details available from initial search for X number of products, run it through LLM once to select top Y number of products for which we get detailed product details through `get_item_details` and again feed it to the LLM for deeper reasoning, comparision and analysis to get our Top Z product recommendations
**See detailed explanation below**
- Guardrails
Safety mecanisms against Prompt Injection, garbage output and content trimming - truncate too large descriptions or summarize them to avoid token bloat and usage-costs.

## RAG
Since we limit our `search_mercari` results to X limits, and just general product meta-data (title, price) available from the search results is not enough for deep-analysis and comparision between product choices, we need detailed product meta-data from individual item-pages. 
Yet at same time, we cannot fetch and use detailed product data for all X results because:
- **Latency and Rate Limits:** It will increase overall Agent response latency and run us into Rate Limits by Mercari, potential server/ip blacklist if considered spam requests. (Fetching 25 product details at 2s per product adds 25 requests and 50s latency).
- **Context Window and Cost:** Passing full product details for X results will increase context window size, token usage per search and ultimately resulting in higher per-query cost. It adds more latency for LLM response too.
So we introduce RAG to our pipeline by initially fetching X number of products through Broad Search, these have minimal details available (title, price).
We feed this broad search results to our Agent/LLM to pick top Y candidates for deeper inspection.
We run these Y number of products to fetch detailed product data through individual product page scraping to get detailed meta-data (title, price, description, condition, listing date, seller rating, etc.).
The Agent/LLM is fed these detailed results to present its reasoning and selecting our Top 3 recommendations.
'Example: Broad search can fetch 50 products, Agent first pass picks us 10 products to do deep inspection, out of which 3 top recommendations are made'


# Future Improvements
- Test suites to automate regular testing of LLM Provider uptime (API calls, active key, token/balance availability)
- Test suites to automate regular testing of Mercari Backend (each scraper mecanism working, incase of errors create automated reports or tickets/issues)
- Token, API calls, Backend usage metadata and monitoring to get a overview of how our system is working in terms of speed, usage and cost
- Summary sub-module for large product descriptions instead of truncating it
- Additional Search Backends like Yahoo Auctions, Yahoo PayPay, Sofmap (Used)
- Current-code improvements marked with `!TODO` inline comment (easy-search)
- Add Language Translation (JP->Eng) and currency selector (show price in USD or JPY)

# External Libraries (and their use)


# License