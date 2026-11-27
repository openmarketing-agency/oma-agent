---
name: social-media-analytics
description: Measure post performance and comment reply coverage.
version: 0.1.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [analytics, social-media, engagement]
    related_skills: [composio-analytics]
---

# Social Media Analytics Skill

Measure publishing activity, per-post performance, and how many audience comments the brand has answered. This is a read-only reporting workflow; do not post, reply, or change moderation state.

## When to Use

Use when asked how many posts a connected account published, how each post performed, or how many audience comments were replied to or remain unreplied.

## Prerequisites

Identify the campaign's authorized platform and brand account. Use the account's enabled read-only MCP tools. If connected through Composio, load `composio-analytics`. Discover separate reads for the account's own posts, per-post metrics, audience comments, and replies; having one does not imply having the others. If the authorized account is unclear, ask instead of switching accounts or guessing IDs.

## Quick Reference

Use the platform names and report terms below as discovery queries. They describe provider capabilities, not a promise that the current toolkit, account tier, permissions, or media type exposes them.

| Platform | What to look up and measure | Reply coverage / limitations |
| --- | --- | --- |
| [Instagram](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media) | List the professional account's media; read media likes/comments and eligible media insights such as views, reach, shares, and saves. Count a carousel as one post; treat Stories separately. | Read media comments and their replies. Identify the brand by its Instagram account ID, not by the connected Facebook login. Counts may include replies; promoted or crossposted totals can use a different scope. |
| [Facebook Pages](https://developers.facebook.com/docs/insights/overview/) | List Page-authored posts; read post reactions, comments, and shares where returned. Look for post insights and video views separately from Page-level metrics. | Read post comments and reply pages with Page identity. Keep organic and paid insights separate wherever the provider distinguishes them. |
| [LinkedIn](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/organizations/share-statistics) | List posts by the organization. Discover organizational share statistics for impressions, unique impressions, clicks, likes, comments, shares, and engagement where available. | Look for social-actions comments and replies with actor URNs. Organization access and personal-profile access differ; organizational share statistics cover organic activity, not paid ad performance. |
| [YouTube](https://developers.google.com/youtube/analytics/metrics) | Enumerate channel uploads, then read video statistics for views, likes, and comment count. For in-period views, watch time, average view duration, or subscribers gained, look for an authorized YouTube Analytics report. Keep Shorts/long-form view definitions distinct when comparing. | `commentThreads.list` inventories top-level comments; embedded replies can be partial. Use `comments.list` by parent ID for missing reply pages. Match the author's channel ID. Disabled or inaccessible comments are not a zero. |
| [TikTok](https://developers.tiktok.com/doc/tiktok-api-v2-video-object) | Look for the connected user's video list/query and request `view_count`, `like_count`, `comment_count`, and `share_count` when exposed. These counters are not date-range activity. | The Display API video object gives a comment count, not reply authorship. Look for a separately authorized comment/reply read; otherwise mark reply coverage unavailable. |
| [Threads](https://developers.facebook.com/documentation/threads/insights) | List the account's posts; look for post insights for views, likes, replies, reposts, and quotes, and keep profile insights separate. | Look for post replies or conversation reads and verify the author and parent on each reply. The insights reply count is not a count of brand replies. |
| [X](https://docs.x.com/x-api/fundamentals/metrics) | List posts by the verified user. Request `public_metrics` for likes, replies, reposts, quotes, and available impressions; owned posts may expose additional click or organic metrics. Media views are distinct from post impressions. | Look for conversation reads/search by `conversation_id`; use parent references to match direct replies. An access-plan or search-history limit makes negative reply claims unsafe. |
| [Pinterest](https://developers.pinterest.com/docs/analytics-and-reports/metrics-glossary/) | List Pins by the authorized account or board and deduplicate Pin IDs. Discover Pin analytics for impressions, saves, Pin clicks, outbound clicks, and supported video metrics. | Pin analytics is not a comment inventory. Report reply coverage only if an authorized read exposes the actual comments and reply authors. |

## Procedure

1. **Set scope and check saved data.** State the platform, account, dates, and timezone. Separate “posts published in the period,” “engagement received in the period” (which may include older posts), and “current engagement on posts published in the period.” State whether replies are measured through the report cutoff or as of now. Load `analytics-dataset` and read saved observations for this scope before fetching gaps. For “how did last week's posts perform?”, inventory that week's posts and label counters as lifetime snapshots unless a date-range report is available.
2. **Inventory and measure posts.** Page through the authorized account's published posts; deduplicate by stable post ID, count one per top-level post, and exclude drafts and scheduled-but-unpublished items. Clarify whether reposts are in scope; crossposts on different platforms are distinct platform posts. For each post, obtain ID/permalink, publish time, views, likes/reactions, and comments where exposed. Add only useful metrics such as reach, impressions, shares/reposts, saves, or outbound clicks. Keep the provider definitions and period basis; don't substitute reach or impressions for views. Report the connected platform's count separately from the local OMA publication count.
3. **Inventory comments and classify brand replies.** Page through distinct top-level audience comments on the selected posts by default. Exclude the brand's own comments and nested replies from the denominator. Use a provider field that explicitly identifies a brand reply, or match each reply's parent comment ID and author ID to the verified brand identity. A confirmed brand reply makes that comment **replied** once even if other pages remain; multiple brand replies still count once. Mark **unreplied** only if the relevant replies are fully readable and none are by the brand. If the comment was inventoried but replies or authorship cannot be verified, mark it **unknown**. If comments themselves aren't enumerable, report the denominator as unavailable or partial, not a fabricated unknown count. Only inspect metadata needed to classify; don't save comment text, commenter identities, or private messages.
4. **Report and save.** Give posts published, comments checked, replied, unreplied, and unknown per platform/account, followed by per-post views, likes, displayed comments, and reply counts as available. Name coverage gaps and whether each metric describes period activity or a lifetime snapshot as of collection. Use `analytics-dataset` for stable post IDs, period definitions, scope dimensions, and saving/reading back verified rows. Use a `post` breakdown for individual posts, not as a replacement for account totals.

## Pitfalls

- A displayed comment count can include replies or different visibility scopes. Don't infer unreplied counts by subtraction. For example, 10 inventoried audience comments can produce 6 replied, 2 unreplied, and 2 unknown even if the post displays 18 comments.
- For a reply rate, state the denominator and scope. If you use `replied / (replied + unreplied)`, label it the rate among verified comments and show the unknown count separately.
- Missing permissions, truncated history, hidden comments, and unsupported metrics are not zero. Do not write partial counts as complete totals or infer historical activity from a current lifetime count.

## Verification

Confirm each metric belongs to the intended account and post. For the audience comments actually inventoried, `replied + unreplied + unknown` must equal that inventory count. Report any additional uncounted scope separately when pagination or permissions were incomplete.
