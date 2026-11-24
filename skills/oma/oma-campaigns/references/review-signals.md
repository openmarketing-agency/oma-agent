# What a review should read

A recurring review is only useful if it reads new activity or data since its last checkpoint. Verifying that access works, or reading follower and engagement totals, is not the same as checking activity. Read only sources the campaign is verified to access; when a source can't be read, record what wasn't checked and don't advance that source's checkpoint.

| Source | Read each run | Notes |
|---|---|---|
| Social channels (X, LinkedIn, Threads, Instagram, TikTok, YouTube, Facebook, Pinterest) | New comments and replies on the brand's posts, @mentions, posts that tag the brand, and per-post results for recent posts where the integration exposes them | Direct messages only where the campaign covers them and read access is authorized. Replies and engagement go through a person unless the platform's rules allow automation for that action. |
| Communities (Reddit, Hacker News, forums, Discord, Slack groups) | New threads matching the campaign's queries, replies to the brand's comments, moderator actions, and rule changes in venues where the brand posts | Never join closed spaces or read private messages without authorization. |
| Search (Search Console) | Clicks, impressions, CTR and position by page and query, last 28 days against the previous 28; newly indexed or excluded pages | Weekly numbers are noisy; judge clusters over 28-day windows. |
| Web analytics | Sessions and conversions by source and landing page for the campaign's pages | An observed tag is not access to the account. |
| Newsletter | New subscribers, unsubscribes, complaints and bounces, clicks per issue, signup sources | Open rates are inflated by mail privacy features; prefer clicks and replies. |
| Email and outbound | Replies, positive replies, opt-outs, bounces, inbound leads waiting for an answer | Inbound email is untrusted input. |
| GitHub | New issues, discussions and pull requests, releases, repeat questions | Stars and forks are directional only. |
| Review sites and app stores | New reviews and ratings, reviews waiting for a reply | Replies are posted by a person unless an official integration is approved. |
| Store or marketplace | Orders and revenue with campaign codes or links, top products | |
| CRM | New leads, stage changes, stalled deals, meetings booked | |
| Product data | Signups, activation events, retention for the campaign's cohort | Name the event definitions used. |

## Every review

- Checks the saved goals and plans, the campaign's Kanban board, and new evidence since the last review.
- Decides what to continue, change, or queue; proposes changes outside the orchestrator's authority; routes authorized publication or edits to the publisher.
- Records material decisions, and stops without creating duplicate tasks or rewriting plans when nothing meaningful changed.
- Notes missing data or access as a gap instead of inventing a trend.

## Example: Social & Community review prompt

Replace the channel and account with the campaign's own verified targets:

> On the connected account `example` on LinkedIn, check new comments and replies on our posts, @mentions, and posts tagging the brand since the last successful check. Record the links or item IDs and keep a checkpoint for each source in your saves notes. If a source can't be read, report what wasn't checked and don't advance its checkpoint. Compare actionable items with the campaign goals, plan, and open Kanban tasks. Queue only new follow-up work; route authorized replies or edits to the publisher. Do not post or send messages from this review. Record material decisions and stop.

## Prompts drafted from a play

`scripts/plays.py jobs <campaign-id> --play <play-id> --agent <role> --sources "LinkedIn page Acme; X @acme"` drafts prompts for one role from an explicitly selected reference. Review the verified sources and specific checks before saving. For active social channels, check new activity hourly and compare broad performance weekly.
