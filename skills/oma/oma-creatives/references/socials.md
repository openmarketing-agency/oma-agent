# Socials Procedure

`collect.py organic` applies these rules; this page says what it collects and how to read the result.

## Selection (per platform, fixed)

1. Take the latest 25 posts by `posted_at`, excluding pinned posts unless they fall inside the latest 25 by date.
2. From mature posts (older than 48 hours) in the last 90 days, take the top 10 by `engagement` (likes + comments + shares + saves, whichever the platform shows).
3. Combine both sets without duplicates, so each platform has up to 35 posts in `posts`. A record in both sets gets `selected_by: [latest, top]`. Earlier records stay in `history`.
4. Reposts and retweets without their own media or caption are skipped. Quote posts and duets count as posts.

## What a logged-out visitor can see

Collection never logs in. Where a platform stops the feed, the platform's coverage is `limited` with `visible_count`, and top posts are ranked among the visible ones only.

| Platform | Route | Typical logged-out view |
| --- | --- | --- |
| instagram | Browser; each post's page metadata | About 9 to 12 latest posts, then a login dialog. Likes, comments, date, caption, image or video. |
| tiktok | Browser for the profile list; each video's page data over HTTP | The full recent feed; exact time, plays, likes, comments, shares, saves; videos download. |
| facebook | Browser; the page's own Close button on the login dialog | About 20 to 35 recent posts; reactions, comments, shares where shown. |
| x | Browser; each post's page | About 5 latest posts; views, likes, reposts; the post time comes from its ID. |
| linkedin | Browser; Dismiss on the sign-in prompt | About 8 to 18 company posts; reactions, comments; the time comes from the activity ID. |
| youtube | Public RSS feed over HTTP | The latest 15 uploads with views and likes; comments are not in the feed. |
| pinterest | Public RSS feed over HTTP | About 25 recent pins; save counts are not public, so no top pins. |
| threads | Browser; each post's page | About 15 posts; views, likes, replies, reposts. |
| bluesky | Public AppView API over HTTP | The full feed with likes, reposts, replies, quotes. |
| reddit | Browser (the JSON API refuses logged-out requests) | The account's recent submissions with score and comments. |

## Per platform

| Platform | What to capture | Notes |
| --- | --- | --- |
| instagram | Feed posts, reels, carousels (all slides) | Engagement = likes + comments; views for reels when shown |
| tiktok | Videos | Views, likes, comments, shares; note sounds by name |
| facebook | Page posts | Reactions, comments, shares |
| x | Posts with their own text or media | Likes, reposts, replies, views; capture threads as one record with `thread_length` |
| linkedin | Company page posts, founder posts if listed in `gtm.md` (for `own`, founder profiles linked from the verified site) | Reactions, comments, reposts |
| youtube | Videos and Shorts | Views, likes, comments; thumbnail + first 30 seconds summary in `structure` |
| pinterest | Pins created by the account (not repins of others) | Saves, comments, reactions when shown; record the board name in `structure` |
| threads | Posts | Likes, replies, reposts |
| bluesky | Posts with their own text or media | Likes, reposts, replies, quotes |
| reddit | Posts by the brand's account | Score, comments, subreddit |

## Account snapshot

At the top of each `index.yaml`, record `handle`, `profile_url`, `followers`, `captured_at`, and `posts_last_90d` (count, or `unknown`).

## Record

```yaml
account:
  handle: "@example"
  profile_url: https://www.instagram.com/example/
  followers: 12400
  posts_last_90d: 38
  captured_at: 2026-01-15T09:00:00Z
coverage:
  status: checked            # checked | limited | blocked | not_found | not_checked
  date: 2026-01-15
  note: ""
  visible_count: 12          # limited only: how many posts a logged-out visitor could see
  proof: {url: https://www.instagram.com/example/, reason: login_limit, screenshot: research/competitors/<id>/socials/instagram/proof.png}
posts:
  - id: c3xyz                # platform post id, slugified
    url: https://www.instagram.com/p/C3xyz/
    posted_at: 2026-01-10T14:32:00Z
    captured_at: 2026-01-15T09:00:00Z
    immature: false
    selected_by: [latest, top]
    format: carousel
    caption: "Full caption text as posted"
    hashtags: [ai, startup]
    media:
      - research/competitors/<id>/socials/instagram/c3xyz/media-1.jpg
    metrics: {likes: 820, comments: 44, shares: null, saves: null, views: null}
    engagement: 864
    engagement_rate: 0.0697   # engagement / followers, or null
    hook_type: problem
    angle: pain
    structure: "Slide 1 pain question, slides 2-5 steps, slide 6 CTA to link in bio"
    promoted: false
    winner: true
    winner_reason: engagement_outlier
    media_pruned: false
    reuse: not_permitted
```

Store media paths relative to `oma/brand/`, as in the example.
