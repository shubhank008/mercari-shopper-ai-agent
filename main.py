"""
Mercari AI Shopper — Main Entry Point and Interactive CLI.
"""

import sys
import asyncio
import argparse
import logging
from src.agent.harness import AgentHarness
from src.tools.formatter import print_banner, print_search_results_table, print_llm_response

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main")

# Use by passing `query` parameter directly to main.py like: `main.py --query I am looking for a Seiko 5 under 25000`
async def run_single_query(harness: AgentHarness, query: str):
    """
    Executes a single search query and displays results.
    """
    print_banner()
    logger.info(f"Processing query: '{query}'")

    final_text, items, provider, tier = await harness.run(query)

    if items:
        print_search_results_table(items, tier)

    print_llm_response(final_text, provider)

# Default behavior if no Args are passed while running main.py
async def run_interactive_loop(harness: AgentHarness):
    """
    Runs interactive CLI shopping session.
    """
    print_banner()
    print("\nType your shopping query below (or 'exit' / 'quit' to stop):\n")

    while True:
        try:
            user_input = input("\n[You] > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nThank you for using Mercari AI Shopping Assistant, Goodbye.")
                break

            final_text, items, provider, tier = await harness.run(user_input)

            if items:
                print_search_results_table(items, tier)

            print_llm_response(final_text, provider)

        except KeyboardInterrupt:
            print("\nSession interrupted. Exiting...")
            break
        except Exception as e:
            logger.error(f"Error executing query: {e}")


def main():
    parser = argparse.ArgumentParser(description="Mercari Japan AI Shopping Assistant")
    parser.add_argument(
        "--query",
        type=str,
        help="Single shopping query in natural language (e.g. 'Find a Macbook 13 under 50000 yen')"
    )
    args = parser.parse_args()

    harness = AgentHarness()

    if args.query:
        asyncio.run(run_single_query(harness, args.query))
    else:
        asyncio.run(run_interactive_loop(harness))


if __name__ == "__main__":
    main()