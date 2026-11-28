# Ads Procedure

`collect.py ads` applies these rules. All four libraries are public and are read logged out through the browser; none needs an account.

## Libraries

| Library id | Searched by (from `sources.yaml`) | What the collector reads |
| --- | --- | --- |
| meta | The Facebook page's ID, found from `page_url`; a keyword search filtered to the advertiser's name only as a fallback | All countries, active and inactive: Library ID, run dates, status, variant count, copy, CTA, landing URL, media (videos load card by card; a card without media is opened on its own page). The page answers HTTP 403 while rendering normally, which is not a block. |
| google | The domain's advertiser accounts, or `advertiser_id` | Each creative's page in English: format, last-shown date, variation count, every variation's image; first-shown dates only where listed. |
| linkedin | The company's numeric ID, found from `company_url`; an advertiser-name search filtered to that exact name as a fallback | Each ad's page: copy, format, advertiser, payer, image or video, run dates and impressions where shown. Landing URLs and active status are not public. |
| tiktok | `advertiser`, searched country by country across the EU, EEA, UK and Switzerland (`countries` narrows it) | The library covers ads shown in those countries only. An ad found in several countries is stored once with every region. The search runs only when the chosen country shows in the form; from networks the library does not serve it offers no countries, and the result is `not_checked`, not `checked`. |

Set a library to `{skip: reason}` in `sources.yaml` when it doesn't fit the target (for example LinkedIn for a consumer ecommerce brand); it is recorded as `not_checked` with the reason.

An empty result counts as `checked` only when the library's own page says there are no ads ("0 results", "0 ads"). A results list that did not load is `not_checked`. A bot challenge stops that library with `blocked`, a proof screenshot, and the countries or pages already done.

## Selection (per library, fixed)

1. Group near-identical ads (same hook and visual, different size or copy tweak) into one concept. Count them in `variant_count`.
2. Take active concepts, sorted by `days_running` (longest first), then `variant_count`.
3. Fill the remaining slots up to 20 with inactive concepts, sorted by `days_running`. The rest stay in `history`.

## Landing page

The collector opens each distinct landing URL once (tracking parameters ignored), saves an above-the-fold `landing.png` shared by every ad that links to it, and stores the headlines, description, and visible CTAs in `landing_facts`. While labeling, write the headline, offer, and primary CTA in `landing_summary`. Nothing submits forms or starts checkouts.

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
