"""
Pretty Formatting Utilities for Terminal using Rich.
"""

from typing import List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from src.data_models.query import MercariItem

console = Console()


def print_banner():
    """Prints application header banner."""
    console.print(
        Panel.fit(
            "[bold cyan]Mercari Japan AI Shopper[/bold cyan]\n"
            "[dim]Your personal shopping assistant to find the best products on Mercari Japan[/dim]",
            border_style="cyan"
        )
    )


def print_search_results_table(items: List[MercariItem], tier_used: str):
    """Render retrieved search items in a formatted terminal table."""

    table = Table(title=f"Retrieved Items via [{tier_used}]", border_style="dim")

    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Condition", justify="right", style="gold")
    table.add_column("Price (JPY)", justify="right", style="green")
    table.add_column("Price (USD)", justify="right", style="dim green")
    table.add_column("Latency", justify="right", style="yellow")

    for idx, item in enumerate(items, start=1):
        usd_str = f"${item.price_usd:.2f}" if item.price_usd else "N/A"
        table.add_row(
            str(idx),
            item.title[:45] + ("..." if len(item.title) > 45 else ""),
            (item.condition or "Unknown"),
            f"¥{item.price:,}",
            usd_str,
            f"{item.fetch_time}ms"
        )

    console.print(table)


def print_llm_response(response_text: str, provider_used: str):
    """Render the final LLM recommendation as Markdown."""
    console.print(f"\n[bold green]Recommendations generated via [{provider_used}]:[/bold green]\n")
    md = Markdown(response_text)
    console.print(Panel(md, border_style="green", expand=False))