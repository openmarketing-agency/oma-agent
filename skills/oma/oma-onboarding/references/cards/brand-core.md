# Brand core research

Source URL: {url}

Load `oma-brand` with `skill_view` and do these rows of its **Research and Output** table, in this order, to the depth the skill asks:

1. **Website**: the home, about, product, pricing, help, blog, footer, and sitemap pages. Write positioning, audience, offers, pricing, conversion paths, proof points, company facts, and open questions into `knowledge-base.md`, citing each page.
2. **Social, blog, newsletter, launches**: open the site's header, footer, and contact links and the profiles' own links. Record **every supported platform** (instagram, tiktok, facebook, x, linkedin, youtube, pinterest, threads, bluesky, reddit) in `channels.social` as `verified` with the URL, `not_found` after checking, or `not_checked` with a reason. Verified profiles on other platforms (Discord, GitHub, Product Hunt) are recorded too. Check Product Hunt, Hacker News, and marketplaces for launches.
3. **Website integrations** and **Website technologies** (the optional `wappalyzer` skill).
4. **Public documentation**: the indexed internal reference.

Write `knowledge-base.md`, the reports under `research/` and `docs/public/`, and merge `id`, `name`, `description`, `website`, `channels`, `launches`, `integrations`, `documentation`, and `knowledge_base_file` into the config.

If the source is a website and you verify the brand's official public repository (linked from the site or its docs), run `{python} {board} repository {home} <repository URL>`; a separate card analyses it. Skip this when the board already has a repository card.

Not in this card: the repository analysis, screenshots and assets, the design system, market research, competitors, creatives, the playbook, or campaigns.

**Check:** `{python} {campaign} validate brand {brand}/config.yaml` passes, and every supported platform has a `channels.social` entry.
