# Design System Template

Save as `design/DESIGN.md` and set `design_system.guidelines: design/DESIGN.md` in `config.yaml`. Campaign agents read this before making any creative, so write each rule so someone can follow it without seeing the source.

Build it from three sources: the verified website pages and screenshots, the official brand or press kit, and the brand's own creatives under `research/own/` (collected by `oma-creatives`). Base every rule on what was observed. Label a rule `(inferred)` when it generalizes from fewer than three examples. Write `not observed` for a section the sources don't cover. Exact values live in `config.yaml` (`palette`, `fonts`, `logos`); refer to them by role, such as `palette.primary`, rather than repeating them here.

Organize it in three levels that build on each other: **Foundations (atoms)** are single brand values, **Components (molecules)** combine foundations into small pieces the brand repeats, and **Layouts (organisms)** combine components into whole creatives or page sections. Add a component only when it appears in at least 3 of the brand's own creatives or website pages, and link those examples; a piece seen fewer times is a one-off, so leave it out rather than inventing a component to fill the level. Describe sizes and positions as proportions (for example, "logo about 10% of the width, top-left"), not pixel values measured from screenshots.

Link each component and layout to the records that show it, using brand-relative paths such as `research/own/socials/instagram/index.yaml` with the post `id`. These links are examples to study. Follow the `oma-creatives` Use Rules: the media is not an input, style reference, or template for generation.

```markdown
# Design System: <Brand name>

- **Last updated:** YYYY-MM-DD  ·  **Sources:** N website pages, brand kit (yes/no), N own posts and N ad concepts across <platforms>

## Foundations (atoms)
### Logo
Variants (`logos.<name>`), when to use each, clear space, minimum size, allowed backgrounds, what to avoid.
### Color
Roles from `palette` and where each appears (backgrounds, text, accents, calls to action). Usual combinations and contrast pairs.
### Typography
Roles from `fonts` (display, headline, body, caption): weight, case, and relative size. Note which roles appear on web, social, or both.
### Imagery and illustration
Photo style (subjects, lighting, crop, people or product), illustration and icon style, textures and backgrounds.
### Grid and spacing
Margins, spacing rhythm, and alignment habits on the website and in creatives.

## Components (molecules)
One subsection per repeated piece, such as a logo and tagline lockup, a headline and call-to-action block, an offer or price badge, a testimonial card, a website button or card, or a caption sign-off. Only pieces seen in at least 3 examples.

### <Component name>
- **Built from:** the foundation roles it uses (for example, `fonts.display` headline, `palette.accent` button, `logos.mark`).
- **Structure:** order, alignment, and proportions of its parts.
- **Used in:** the channels and layouts where it appears.
- **Variants:** light or dark, sizes, or wording patterns observed.
- **Examples:** 3 or more links to records or screenshots.

## Layouts (organisms)
One subsection per platform and format that the brand actually uses, such as `Instagram carousel`, `TikTok video`, `Facebook ad`, `LinkedIn image post`, `Pinterest pin`, `YouTube thumbnail`, or a website hero.

### <Platform> <format>
- **Canvas:** aspect ratio and safe areas observed.
- **Composition:** which components it uses and where each sits (for example, "headline block top-left, product center, logo lockup bottom-right"); text density.
- **Type on image:** which font role, case, length of on-image text.
- **Color and imagery:** which palette roles and image style recur.
- **Motion and editing (video):** hook in the first seconds, pacing, captions or subtitles, sound use, end card.
- **Copy:** hook type, caption length, call-to-action placement, emoji and hashtag use.
- **Examples:** links to records.

## What performs
Patterns shared by the brand's winners (the `oma-creatives` winner rules), each with its evidence and records. Note patterns the brand uses often that do not perform.

## Website and social differences
Where the website and social creatives differ (for example, a different accent color or typeface on social). Record both and which channel each applies to; don't merge them. List open questions for the brand owner.

## Rules
Do's and don'ts that apply to every creative, from the brand kit or consistent observation: logo misuse, banned colors or claims, required disclaimers, accessibility (contrast, captions on video).

## Coverage
Sources checked, blocked, or not found, with dates. Platforms with a verified profile but no collection.
```
