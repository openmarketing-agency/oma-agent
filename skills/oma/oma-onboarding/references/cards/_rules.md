
## Rules for every onboarding card

- Work only on this card's scope. Other cards own the other stages; do not do their work, even if it looks quick.
- The brand home is `{home}`; the brand record is `{brand}`. Store paths relative to the brand directory.
- Do not write `{brand}/config.yaml` directly. Write the keys this card owns to a YAML file and merge it with `{python} {board} merge-config {home} <file>`, so parallel cards never overwrite each other.
- Do not create or edit skills or memories. Do not change the board or work around its guards (for example by unsetting environment variables); only complete or block this card. Report a gap in your completion summary instead.
- Run scripts by file path with `{python}`. Inline `python -c` and heredocs are refused in card workers.
- Research is read-only, public, and logged out. Never solve or bypass a bot challenge, log in, or submit forms. A blocked source is recorded with its reason, never guessed.
- Finish only when this card's check passes. Then complete the card with a short summary: what was saved, the coverage per source, and anything blocked or unverified. If the check cannot pass, block the card with the exact reason instead of completing it.
