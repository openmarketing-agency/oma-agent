# Designing plays

Campaigns start from ideas in `ideas/catalog.yaml`. The bundled plays are only examples: each shows one or a few catalog ideas worked out for a made-up business, with a team where every role produces something each run. Use them to see how a good campaign is built, then design what this business needs. Don't copy an example's business, names or numbers.

## 1. Understand the business first

Before opening the catalog, write down (in your working notes, not the records):

- **The goal that matters now**, in business terms: revenue, qualified leads, activated users, sales, retention, reputation. Take it from the playbook.
- **How money and customers arrive today.** Look in the brand research and connected data: the CRM, the store, inbound leads, past launches. When it isn't there, note it as missing rather than guessing.
- **The buyer and how they buy:** who decides, where they look for answers, what makes them trust a vendor, how long it takes.
- **Where demand already exists:** searches, communities, marketplaces, referrals, existing customers, inbound requests, competitor audiences.
- **What the team can actually supply:** founder time and willingness to post, footage, expertise, budget, approvals turnaround.
- **What access is verified:** connected integrations and accounts, analytics, CRM. A public profile or a page tag is not access.
- **What has already been tried,** and what happened.

## 2. Find the leverage

Pick the few moves with the biggest gap between what is possible and what is happening now. Typical signs:

- Leads or customers arrive but go unanswered or unconverted: fix that before buying attention.
- Buyers search for the problem and the brand is absent: search and comparison content.
- Communities discuss the problem: participation, then launches.
- The product is visual or demo-friendly and the audience watches short video: a video engine.
- The founder has a story and an audience nearby: founder-led social.
- Trust is the bottleneck: proof, reviews, case studies.
- A marketplace, app store or partner ecosystem is where buyers shop: a listing or partnership play.

## 3. Pick ideas, then use a play as the reference

- **Pick** the catalog ideas that carry the leverage you found. Read the catalog with `scripts/plays.py ideas`; `for` is only a hint about which businesses an idea usually suits. Remix an idea's channel, format or audience when that fits better. If nothing fits, explain the reasoning in your handoff; do not add campaign fields.
- **Find the reference.** Each idea's `example` names the play that shows a similar campaign. Read its `play.yaml`, `rules.md` and `example.md`. When the idea needs a different shape, read the play closest to it: a reply desk looks like `buying-intent-listening`, a weekly content engine like `seo-blog-engine` or `daily-shorts`, a time-boxed push like `show-hn-launch`.
- **Design for this business.** Keep the reference's shape where it fits: roles by craft, a `per_run` for every role, deliverables that ship, the review job, the rules. Change channels, roles, deliverables, cadence and rules to match the business. Save a custom play when they differ: `scripts/plays.py new <new-id> --from <play-id>`, or `--blank` when nothing is close.
- **Combine** ideas into one campaign when they share a team and an outcome, for example community questions feeding an SEO engine. Make one play with one outcome rather than two campaigns chasing the same result.

Ideas the examples don't show directly, and the bundled skills to draw on:

| Business need | Catalog area | Bundled skills to draw on |
|---|---|---|
| App installs | App store optimization | `aso`, `image`, `ab-testing` |
| Marketplace sales | Marketplace listings | `copywriting`, `image`, `social-proof-and-testimonials` |
| Partner reach | Co-marketing and integrations | `co-marketing`, `collabs-and-cross-promotion` |
| Pipeline from events | Webinars and events | `events`, `emails`, `lead-magnets` |
| Word of mouth | Referral programs | `referrals`, `emails`, `offers` |
| Linkable demand | Free tools | `free-tools`, `programmatic-seo` (only with real value per page) |
| Activation and retention | Lifecycle email | `emails`, `onboarding`, `churn-prevention` |
| Conversion | Pricing and signup CRO | `cro`, `pricing`, `signup`, `ab-testing` |

Use `skills_search` and `skill_view` to read the bundled skills before you rely on them.

## 4. Shape the play

- **Outcome:** one business result, specific to this brand, measurable when data exists.
- **Team:** orchestrator, publisher, and makers by craft (researcher, writer, producer, scout, responder and so on). Give each role one clear job, a `per_run` that says what it hands over every run, the toolsets it needs, the channels it reads, and `untrusted_input: true` if it reads public or inbound content. Only the publisher writes outside OMA.
- **Deliverables:** concrete, countable things on a cadence the team can sustain. A campaign that only monitors isn't a campaign.
- **Jobs:** the orchestrator's review plus any independent recurring check a specialist really owns. Checks name activity to read, not access to verify.
- **KPIs:** a few leading signals and the lagging business result. Targets come after a baseline.
- **Limits:** caps that protect accounts, domains and budgets. Platform rules go in the channel files, not here.
- **Example:** `example.md` shows the play running for this business: Business, Why this idea, Campaign, Team with each role's per-run output, First week.
- **Slots:** what must be filled from this business before install.
- **Kickoff:** the first tasks that make progress visible in the first days.

## 5. Write the rules

`rules.md` is what the agents read while working, so make it practical:

- What good looks like, in concrete terms.
- The rhythm: weekly routine or phases.
- Definition of done for each deliverable.
- Non-negotiables: the legal and craft limits for this kind of work, plus a line pointing to its `channels/<channel>.md` rules. For a new channel, look up the platform's current official rules and save them to `oma/plays/channels/<channel>.md` with links and the date checked. If the exact action is not permitted or its support cannot be verified, leave it unpublished or hand it off where permitted.
- How to measure, and when it is too early to judge.
- Common failure modes.
- Sources to re-check.

## 6. Check it

Run `scripts/plays.py validate <play-id>` and fix every error. Then read it as the user would: would this plan, done well, move the business toward its goal? If it would read the same for any brand, make it more specific.

## What never changes

Keep one orchestrator and one publisher. Route supported writes through authorized official integrations and respect platform and venue rules. For new OMA publications, `yolo` auto-approves without asking; `approve` and `control` require human approval of the exact revision. Do not apply publication approval to authorized edits of existing live content. `control` runs no campaign cron. Keep verified rather than assumed access, no invented metrics, testimonials or claims, and no terminal for roles that read untrusted content.
