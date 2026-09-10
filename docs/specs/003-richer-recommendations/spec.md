# Rich recommendation presentation

## Goal

Make webchat recommendation results as useful as the CLI while keeping the browser presentation focused on shopping decisions rather than execution internals.

## User experience

- The response begins with a concise recommendation summary and the assistant's reasoning.
- A full comparison table shows every shortlisted item returned by the harness, with rank, title, price, condition, likes, seller rating, seller name, and Mercari link.
- The final section shows the top three recommended listings as visual cards.
- Cards show recommendation reasoning, a large bold price, explicit condition and seller labels, seller name, rating count, likes, and every available image.
- Clicking any product image opens a dismissible enlarged lightbox. The image remains keyboard accessible and does not navigate away from the conversation.
- Provider name, scraper tier, latency, and turn count are not displayed as recommendation metadata.

## Data contract

The API returns `shortlist` for all retrieved listings and `products` for the top three display cards. The existing LLM recommendation remains the source of recommendation reasoning. Because the current harness returns prose rather than structured ranking, the web adapter uses the first three retrieved listings as the visual recommendation set and labels them as assistant-selected results only when the assistant prose is available. It never invents per-item reasoning or seller data.

Every card and shortlist row receives seller fields from the hydrated `MercariItem`. Missing values render as `Not available`, never as scraper-tier names. `source_tier` is excluded from public presentation.

## Acceptance criteria

- No provider, scraper, latency, or turn metadata appears in the user-facing recommendation result.
- The complete shortlist is rendered before the final top-three cards.
- Prices are visually prominent and bold.
- Labels use `Seller Rating:`, `Total Ratings:`, and `Condition:` wording.
- Seller name is rendered independently from scraper source.
- Product images support click-to-enlarge and an accessible close interaction.
- Existing safe new-tab Mercari links remain intact.
- The response remains useful when optional seller fields or images are missing.
