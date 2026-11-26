# Discovery Sources

Run every source for the brand's `business_type`, in order. Substitute `{term}` with each `frame.category_terms` entry, `{brand}` with the brand name, and `{market}` with each market, or omit it for `global`. Log every source in `research/competitors/discovery.md` with the date, the exact queries, the candidate count, and `checked`, `blocked` (with the reason) or `not_checked` (with the reason).

Stop adding new candidates at 30. Keep logging the sources you still run, because their mentions still count toward ranking.

## Core sources (every business type)

| # | Source id | How | Queries / targets |
| --- | --- | --- | --- |
| 1 | `brand_site` | `web_extract` the brand's comparison, "vs", alternatives, integrations, and pricing pages, plus its sitemap | Any product the brand names as a rival or alternative (set `named_by_brand: true`) |
| 2 | `serp_category` | `web_search` | `{term}`, `best {term}`, `{term} {market}` |
| 3 | `serp_alternatives` | `web_search` | `{brand} alternatives`, `{brand} vs`, `{term} alternatives` |
| 4 | `serp_ads` | `browser_exec` on a search results page | Advertisers shown as sponsored results for `{term}`. Record the domains. Mark `blocked` if a CAPTCHA appears |
| 5 | `communities` | `web_search` scoped to reddit.com and news.ycombinator.com | `{term} recommendations`, `{term} vs`, `what do you use for {job}` |
| 6 | `meta_ad_library` | `browser_exec` on facebook.com/ads/library, all ads, keyword search | `{term}`, with the country set to the brand's market or "All" |

## Extra sources by business type

| Business type | Source id | How | Queries / targets |
| --- | --- | --- | --- |
| `saas` | `review_sites` | `web_search` / `web_extract` | G2 and Capterra category and alternatives pages for `{term}` and `{brand}` |
| `saas` | `product_hunt` | `web_search` scoped to producthunt.com | `{term}`, plus launches in the same topic in the last 12 months |
| `open_source` | `github` | `web_search` scoped to github.com, or the GitHub topic pages | Topic pages and repos for `{term}`, plus awesome-lists containing `{term}` |
| `open_source` | `alternativeto` | `web_search` scoped to alternativeto.net | `{brand}`, `{term}` |
| `ecommerce` | `marketplaces` | `web_search` | `{term}` on Amazon, Etsy, Daraz or the main local marketplace for the market, plus the top storefront brands |
| `ecommerce` | `tiktok_creative_center` | `browser_exec` on the TikTok Creative Center Top Ads | Industry and keyword closest to `{term}`. Mark `blocked` if a login is required |
| `ecommerce` | `shopping_serp` | `web_search` | `buy {term} {market}`, `{term} price {market}` |
| `local` | `local_search` | `web_search` / maps results | `{term} near {city}`, `best {term} in {city}` |
| `local` | `local_directories` | `web_search` | `{term} {city}` on the main local directories and review sites for the market |
| `marketplace` | `both_sides` | `web_search` | Run the core queries once for the supply side and once for the demand side |

For `other`, run the core sources plus the type that fits best, and say which one you chose in `discovery.md`.

## Candidate hygiene

- Merge duplicates: the same product under several domains, an old name and a rebrand, or a parent company and its product. Use the product as the candidate.
- Listicles, agencies that review tools, and media sites are sources, not candidates.
- Do not add candidates from memory or general knowledge. Every candidate needs at least one logged source.
