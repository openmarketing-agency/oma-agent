# Socials Procedure

## Selection (per platform, fixed)

1. Take the latest 25 posts by `posted_at`, excluding pinned posts unless they fall inside the latest 25 by date.
2. From posts in the last 90 days, take the top 10 by `engagement` (likes + comments + shares + saves, using whichever the platform shows).
3. Combine both sets without duplicates, so each platform has 25 to 35 posts. A record in both sets gets `selected_by: [latest, top]`.
4. Reposts and retweets without their own media or caption are skipped. Quote posts and duets count as posts.

## Per platform

| Platform | What to capture | Notes |
| --- | --- | --- |
| instagram | Feed posts, reels, carousels (all slides) | Engagement = likes + comments; views for reels when shown |
| tiktok | Videos | Views, likes, comments, shares; note sounds by name |
| x | Posts with their own text or media | Likes, reposts, replies, views; capture threads as one record with `thread_length` |
| linkedin | Company page posts, founder posts if listed in `gtm.md` | Reactions, comments, reposts |
| facebook | Page posts | Reactions, comments, shares |
| youtube | Videos and Shorts | Views, likes, comments; thumbnail + first 30 seconds summary in `structure` |
| reddit | Posts by the brand's account | Score, comments, subreddit |
| threads | Posts | Likes, replies, reposts |

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
  status: checked            # checked | blocked | not_found | not_checked
  note: ""
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
