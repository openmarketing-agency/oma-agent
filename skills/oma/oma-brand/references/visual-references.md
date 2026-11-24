# Social sources and visual asset inventory

1. **Verify the brand and related sources.** Open the supplied public profile or official site. Follow first-party links in its bio, website navigation, or repository. If a platform blocks direct access, stop there. Use `web_search` to locate the exact handle's linked site, then verify ownership against the first-party site (brand identity and the matching account or corroborating links). Don't treat a search result or same-name account as verification. Do not log in, bypass a challenge, or follow unrelated accounts. Keep social-only brands usable without inventing a website.
2. **Find the logo.** If a verified website is available, check it before using a social avatar. Inspect its official brand or press assets, rendered header and footer wordmarks (including inline SVG or CSS artwork), and declared `logo` metadata. Prefer a verified downloadable original from the website or its asset CDN over a crop. If no original is accessible, use a clean crop of the rendered mark as a visual reference. For a verified Instagram or TikTok profile, check the account avatar and `og:image` only after exhausting available website sources. Treat all results as candidates: view the image, confirm it depicts the brand (not a platform badge, product photo, placeholder, or another account), and verify the file decodes. A generic page preview or favicon is not evidence of an official logo. Save authorized files under `logos/` using their real extension, not a temporary CDN URL. Note the source and permission in `design/assets.md`. Without reuse evidence, keep the capture as a visual reference, report the logo gap, and offer to use an approved upload. Do not generate a replacement logo.
3. **Capture useful pages before finishing setup.** Capture the accessible supplied profile, verified homepage, and distinct high-value pages linked from them, such as About, a collection, a representative product, pricing, or public docs. Capture up to 10 distinct public pages per brand on a first pass. Count each page once, even if it has mobile views or numbered screenshot sections. Use full-page desktop captures; add mobile views of the homepage and one important profile or product page where layout differs. Wait for branding and media to render and scroll normally to load lazy images. For long documents, keep consecutive numbered sections; for feeds or pages with a separate scroll container, add useful viewport captures as you scroll the public content. Stop at the public login boundary; do not capture authenticated, empty, login-only, block, or error pages.
4. **Save only verified files.** Start in a private browser workspace directory. Inspect the captures, keep distinct useful views, and copy them to `<home>/oma/brand/screenshots/` with stable page, viewport and section names. Preserve existing files and use a new filename rather than replacing a custom capture. Verify each file decodes at the recorded dimensions, and add one `screenshots` item per saved file with its brand-relative `file` and actual public `source_url`. Record date, viewport, section and any missing coverage in `design/assets.md`. Report the logo source and capture count, and distinguish blocked pages from successful alternatives.
5. **Collect every distinct visual found on the reviewed pages.** Inventory all logo variants, illustrations, icons, backgrounds, and images alongside the screenshots. Scan the site's official brand/press kit as well as the reviewed pages, and include lazy-loaded and mobile-specific art once it renders. Review category assignments rather than blindly trusting filenames. Deduplicate across pages by source and by file content; do not treat a resized duplicate as a new asset. Save every verified, authorized original under its matching brand directory and record source, reuse evidence, and saved versus unavailable status in `design/assets.md`. Keep inline crops and CSS-only artwork as visual references unless separately approved for reuse. Report counts per category and pages, plus blocked, unlicensed, or truncated coverage. Do not traverse the whole site indefinitely or fetch hidden/private assets.

## Browser helper

With `browser_exec`, open and verify each public page and wait until it renders. Call the bundled helper on the current tab, using the absolute `skill_dir` returned by `skill_view(name: oma-brand)`:

```python
# Capture a verified public brand page
import json
import os
import runpy
from pathlib import Path
from tempfile import mkdtemp

capture_page = runpy.run_path(str(Path(SKILL_DIR) / "scripts" / "visual_reference.py"))["capture_page"]
output = Path(mkdtemp(prefix="brand-visuals-", dir=os.environ["BH_AGENT_WORKSPACE"]))
result = capture_page(VERIFIED_PAGE_URL, output, PAGE_AND_VIEWPORT_SLUG, js=js, cdp=cdp)
print(json.dumps(result))
```

Replace the uppercase parameters with literal values: installed skill directory, verified final URL, and a lowercase hyphenated name such as `home-desktop`. `logo_candidate` identifies the locally extracted PNG and its source, when found. A source pointing at the page rather than an image indicates a rendered crop. Treat it and the `image_candidates` URLs as candidates, not confirmed logos. Verify the PNG visually and keep a higher-quality authorized original if available. `blocked` means don't save a capture; `login_overlay` means only retry after using the page's own visible Close button if it offers one and leaves the public content accessible. Never remove an overlay with scripts or alter access controls. `partial` or `capture_failed` means try `capture_screenshot()` on that already verified tab and save useful viewport sections instead. A partial scroll capture is not a full page. If the helper path isn't visible to the browser executor or the browser lacks CDP screenshot support, use its normal viewport capture. For logo lookup without a browser, inspect first-party HTML metadata with the available read-only fetch tool and verify the returned image; don't count metadata extraction as a screenshot.

`asset_inventory` points to the per-page JSON with all discovered candidates and their IDs; `asset_counts` summarizes it. Read that file, not just the primary logo or a handful of previews. If `asset_inventory_limited` is true, record the limit and use the relevant collection or brand-kit links within the page budget to cover the gap. For public approved CDN and kit files, retrieve verified originals with the normal read-only tools. Verify types and decode images before promotion; never copy executable page code or unsanitized active SVG into a served brand record. For batches of approved same-origin images or inline references, stay on that page at the same viewport and call the helper's `stage_assets` function with up to 12 selected IDs per call. Repeat for remaining authorized candidates; 12 is a batch size, not an onboarding limit:

```python
# Stage verified allowed visual assets
import json
import runpy
from pathlib import Path

stage_assets = runpy.run_path(str(Path(SKILL_DIR) / "scripts" / "visual_reference.py"))["stage_assets"]
print(json.dumps(stage_assets(INVENTORY_PATH, STAGING_PATH, APPROVED_IDS, js=js, cdp=cdp)))
```

Pass the returned inventory path and a private staging path, and use only IDs with verified reuse evidence or explicitly requested visual-reference captures. A PNG rasterized from a source can differ from the original's size or format. Match category files to actual content, keep distinct authorized variants, and do not promote cropped references as originals. If an asset changes between inventory and staging, capture a fresh inventory rather than changing its URL manually.
