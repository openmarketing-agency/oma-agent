# Market research

Load `oma-brand` and do its **Market** row: dated sources for segments, demand, trends, geography, and buying triggers, separating estimates from facts, in `research/market.md`. Use `knowledge-base.md` for the brand's positioning; competitor research runs separately.

Merge `research: {market_report: research/market.md}` into the config.

**Check:** `research/market.md` cites a dated source for every claim; `{python} {campaign} validate brand {brand}/config.yaml` passes.
