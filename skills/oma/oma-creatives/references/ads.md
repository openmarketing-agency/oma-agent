# Ads Procedure

## Libraries

| Library id | Where | Search by | Fields available |
| --- | --- | --- | --- |
| meta | facebook.com/ads/library (All ads) | Page name; country = brand market or All | Media, primary text, headline, CTA, landing URL, start date, active status, platforms, variant count; EU reach and demographics on EU-served ads |
| google | adstransparency.google.com | Advertiser name or domain | Image, video or text creative, first and last shown dates, regions, format (search, YouTube, display) |
| linkedin | linkedin.com/ad-library | Company name | Copy, creative, CTA, dates, impression range when shown (B2B targets) |
| tiktok | TikTok Creative Center Top Ads; TikTok ad library for EU ads | Brand name, industry, keyword | Video, caption, objective, engagement signals (consumer and ecommerce targets) |

Skip a library that doesn't fit the target (for example LinkedIn for a consumer ecommerce brand), and record it as `not_checked` with the reason.

## Selection (per library, fixed)

1. Group near-identical ads (same hook and visual, different size or copy tweak) into one concept. Count them in `variant_count`.
2. Take active concepts, sorted by `days_running` (longest first), then `variant_count`.
3. Fill the remaining slots up to 25 with inactive concepts, sorted by `days_running`.

## Landing page

For each ad concept, open its landing URL once, take an above-the-fold screenshot (`landing.png`), and note the headline, offer, and primary CTA in `landing_summary`. Do not submit forms or start checkouts.

## Record

```yaml
coverage:
  status: checked            # checked | blocked | not_found | not_checked
  date: 2026-01-15
  note: ""
ads:
  - id: meta-123456789       # <library>-<library ad id>
    library: meta
    url: https://www.facebook.com/ads/library/?id=123456789
    platforms: [facebook, instagram]
    format: video
    primary_text: "Ad body text as shown"
    headline: "Headline as shown"
    cta: "Sign up"
    landing_url: https://example.com/lp
    landing_file: research/competitors/<id>/ads/meta/meta-123456789/landing.png
    landing_summary: "Free trial offer, headline about speed, single signup CTA"
    media:
      - research/competitors/<id>/ads/meta/meta-123456789/video.mp4
    first_seen: 2025-12-01
    last_seen: 2026-01-15
    active: true
    days_running: 45
    variant_count: 4
    regions: [EU]
    reach: null              # EU reach when shown
    hook_type: demo_first
    angle: speed
    structure: "0-2s product demo, 3-8s before/after, 9-12s offer + CTA"
    promoted_from: null      # instagram/c3xyz when it reuses an organic post
    winner: true
    winner_reason: long_running
    media_pruned: false
    reuse: not_permitted
```
