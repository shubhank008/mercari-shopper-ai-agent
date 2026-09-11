# Implementation plan

## Global constraints

- Keep recommendation prose as untrusted text and insert it through `textContent`, never HTML interpolation.
- Keep seller fields and links sourced from typed Mercari data.
- Do not expose credentials, raw provider responses, or session headers.
- Preserve the current comparison, safe external links, and accessible image lightbox.

## Steps

1. Add a deterministic prose partitioner in the web presentation layer.
2. Return structured recommendation sections and conclusion from the API.
3. Render sections in order and associate ranked reasoning with matching products.
4. Change media CSS to natural aspect-ratio sizing with bounded dimensions.
5. Add parser/API/rendering regression tests and validate the supplied live query.
