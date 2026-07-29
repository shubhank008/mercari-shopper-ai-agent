# mercari-shopper-ai-agent
AI-Agent harness for shopping on Mercari Japan

# Overview
AI Agent to search and recommend products from Mercari (JP) using user's NaturalLanguage prompt.

# Demo

# Setup

# Usage

# Design Architecture
## High Level
User Prompt (Natural Language)-> LLM Provider call + Tool Call (search_mercari)-> Result Injection (LLM)-> Reasoned Recommendation (JSON)-> Output (User Friendly/Natural Language)
## Low Level
- LLM Provider Call
Decoupled-Interface design to add one or more LLM providers for quick switch and scale. Also adds priority-fallback if one provider is down or not available.
- Tool Call (search_mercari)
Multiple scraping mechanisms for a similar fallback approach if one scraper fails. Priority order based on execution time and third-party library usage.
- Guardrails
Safety mecanisms against Prompt Injection, garbage output and content trimming - truncate too large descriptions or summarize them to avoid token bloat and usage-costs.

# Future Improvements
- Test suites to automate regular testing of LLM Provider uptime (API calls, active key, token/balance availability)
- Test suites to automate regular testing of Mercari Backend (each scraper mecanism working, incase of errors create automated reports or tickets/issues)
- Token, API calls, Backend usage metadata and monitoring to get a overview of how our system is working in terms of speed, usage and cost
- Summary sub-module for large product descriptions instead of truncating it
- Additional Search Backends like Yahoo Auctions, Yahoo PayPay, Sofmap (Used)

# External Libraries (and their use)


# License