# Recommendation prose and image layout fix

## Goal

Present the LLM recommendation in the same readable sequence as the CLI without repeating the entire answer in every product card, while preserving image aspect ratios.

## Behavior

- Extract the opening recommendation context, each ranked `Recommendation N` section, and the final conclusion from the LLM prose.
- Show the opening context once above the shortlist comparison.
- Show each ranked recommendation's title, reasoned analysis, and matching product card only in its own section.
- Show the final purchase recommendation or conclusion after the cards.
- If parsing cannot identify sections, show the full recommendation once and use a concise generic card reason rather than duplicating the full prose.
- Product images use natural aspect ratio within a bounded media frame. They are never stretched to the card's content height.

## Acceptance criteria

- The full LLM answer is not repeated three times in final cards.
- Each final pick displays its matching reasoning section when the LLM provides one.
- The final conclusion remains visible after the final cards.
- Images maintain aspect ratio and remain clickable for enlargement.
- Existing comparison and safe Mercari link behavior remains intact.
