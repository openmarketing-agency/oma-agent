# Reference plays

Each folder is a play: one or a few ideas from `ideas/catalog.yaml` worked out for a made-up business. `play.yaml` has the team and what it ships, with a `per_run` output for every role; `rules.md` has the craft, definition of done and non-negotiables; `example.md` shows the play running, from the business to the first week. `catalog.yaml` indexes them and `vocab.yaml` holds the shared vocabulary. Platform rules live in `../channels/`.

Plays are only examples. Campaigns start by picking ideas from the catalog for the business in front of them, then use the play that fits as a reference. Never copy an example's business, names or numbers. Plays designed for a business are saved in `oma/plays/<play-id>/` under the default Hermes home, never here.

| Play | Example business | Shows |
|---|---|---|
| `seo-blog-engine` | Ledgerline, payroll software | Articles on a schedule, from research to publish |
| `show-hn-launch` | Driftless, an open-source Postgres CLI | A time-boxed launch with a demo and a person posting |
| `comment-to-dm` | Fernbloom, skincare | Content that invites comments, and replies to people who asked |
| `abandoned-cart-recovery` | Kestrel Supply, a Shopify store | Email and SMS flows that recover carts |
| `review-asks` | Riverside Family Dental | Review requests, replies and Business Profile posts |
| `podcast-tour` | Halden Advisory, B2B consulting | Pitching shows and preparing each appearance |
| `daily-shorts` | Repwise, a fitness app | Short videos made and published daily |
| `buying-intent-listening` | Tallybook, accounting for freelancers | Finding people asking, publishing permitted replies, answer pages |
| `discord-community` | Lantern Forge, an indie game studio | Fast answers, a living FAQ and weekly events in the brand's own server |
| `search-intent-ads` | Ortega & Lin Immigration Law | Search ads on buying intent with matching landing pages, inside regulated rules |

Channel rules were checked on 2026-11-24. Re-check them every quarter.

Maintainers: after editing a bundled play, run `python3 scripts/plays.py validate` and `python3 scripts/plays.py catalog --write` from the skill folder.
