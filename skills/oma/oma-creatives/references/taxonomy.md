# Labels and Winner Rules

Use only these values. If you use `other`, explain it in `structure`.

- **format:** `image`, `video`, `carousel`, `text`, `story`, `reel`, `short`, `thread`, `other`
- **hook_type:** `question`, `bold_claim`, `stat`, `problem`, `demo_first`, `before_after`, `pov`, `listicle`, `testimonial`, `founder`, `trend`, `meme`, `other`
- **angle:** `pain`, `outcome`, `speed`, `savings`, `social_proof`, `authority`, `comparison`, `urgency`, `feature_demo`, `founder_story`, `ugc`, `education`, `offer`, `novelty`, `identity`, `behind_the_scenes`, `other`

## Winner rules

Set `winner: true` when one of these is true, and put the first matching reason in `winner_reason`:

| Reason | Applies to | Rule |
| --- | --- | --- |
| `long_running` | ads | `active: true` and `days_running` ≥ 30 |
| `many_variants` | ads | `variant_count` ≥ 3 |
| `engagement_outlier` | posts | Not `immature`, and `engagement` ≥ 3 × the median engagement of the mature posts collected for that platform |
| `promoted` | posts | The post was later run as an ad (`promoted: true`) |
