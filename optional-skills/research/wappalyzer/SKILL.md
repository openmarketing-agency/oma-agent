---
name: wappalyzer
description: Identify website technologies for company research.
version: 1.1.0
author: Suraj Jha, Hermes Agent
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    category: research
    tags: [Research, Websites, Technologies, Competitors, Wappalyzer]
    related_skills: [domain-intel, grounded-citations]
---

# Wappalyzer Skill

Identify CMS, ecommerce platforms, analytics and frameworks using the upstream
[Wappalyzer detector](https://github.com/tomnomnom/wappalyzer).
Prefer the existing Camoufox browser through the Camofox plugin, then another
available browser tool, then the upstream Chromium CLI. This is technology
research; a detection is evidence, not proof of a company's internal architecture.

## When to Use

- Research the technologies on a company or competitor website.
- Add a dated technology-stack section to a company research report.
- Compare detected platforms across a user-provided set of websites.

## Prerequisites

Use `terminal` for the helper and `read_file` for its saved output. The Python
interpreter must be the Hermes environment; Node must already be available.
`SKILL_DIR` means the directory containing this file.

Docker startup fetches the pinned Wappalyzer revision from upstream and
prepares its CLI in `cache/research/wappalyzer/<revision>` under the shared
Hermes home. The release image ships the installer and the integration.
Persist the data volume to reuse the completed installation across container
replacements. A failed install is logged during startup and retried on the
next start. See `NOTICE` for upstream attribution.

Outside Docker, Git, Node and npm are needed for one-time setup:

```bash
python SKILL_DIR/scripts/wappalyzer_installation.py
```

The research helper finds this cache automatically. Use `--upstream PATH`
only if the operator already has a separate prepared checkout.

For CLI fallback, Chromium must already be available through Hermes's existing
browser executable resolver. Neither the detector nor browsers are installed at
research time. If a prerequisite is missing, explain it and stop that path.

For Camoufox, use the installed **Camofox plugin** and its configured browser
tools (`browser_navigate`, `browser_console`). If missing, follow that plugin's
setup, or use another available browser. Do not import a plugin's private modules,
change browser configuration, or switch the conversation's toolset.

## How to Run

Check the prepared detector once per research task, before opening any pages:

```bash
python SKILL_DIR/scripts/research.py --check
```

A successful check returns `status: ready` with the resolved path and version.
If it errors, report the missing prerequisite. In Docker, point to the startup
logs and the next restart retry. On a local install, point to the setup command
above. The check only inspects files and finds Node.

1. Open the target through the Camofox plugin's `browser_navigate`. Wait for
   the finished page, then evaluate `scripts/collect.js` with `browser_console`
   on that tab.
2. Save the JSON string returned by the expression as `page.json` where
   `terminal` can read it. The helper expects the decoded object from the
   expression and takes the final page URL from its `url` field.
3. Pass that same final URL to the helper:

```bash
python SKILL_DIR/scripts/research.py https://example.com/ \
  --browser camofox \
  --capture page.json --output technologies.json
```

If the Camofox tools are unavailable or the capture fails, use `browser_exec`
or another available browser tool to navigate and evaluate the same expression.
Run the helper with `--browser browser-exec` and `--capture page.json`. If the
site shows an access denial or a challenge page, report that result and stop.

If neither browser tool is usable, run the prepared upstream CLI:

```bash
python SKILL_DIR/scripts/research.py https://example.com/ \
  --browser chromium-cli --output technologies.json
```

This fallback uses an isolated temporary browser profile, a single page, no
recursive crawl or extra probes, and a 60-second process timeout. It never reuses
the user's interactive browser profile. Record why a browser fallback was needed.

## Quick Reference

| Input/field | Meaning |
| --- | --- |
| `--check` | Verify the detector files and Node before collecting a page |
| `--capture FILE` | Rendered page JSON from the preferred browser |
| `--upstream PATH` | Override the default runtime cache with a prepared checkout |
| `--browser` | `camofox`, `browser-exec`, or `chromium-cli` |
| `--timeout SECONDS` | Process timeout; default 60 |
| `--output FILE` | Save the same JSON also printed to stdout |
| `scanned_at`, `detector` | UTC analysis time and external detector version |
| `technologies` | Upstream names, versions, categories and confidence |
| `basis`, `signals` | Capture mode: matched signal types versus implied technologies |
| `mode`, `limitations` | Actual detection path and missing signal types |
| `status`, `urls` | `ok` or `partial`; CLI navigation errors/statuses |

Exit status is zero for completed analysis, one for errors or partial CLI results.
Errors are JSON on stderr; failed scans must not be represented as an empty stack.

## Procedure

Research only the websites needed for the question. Inspect one page first; when
more pages matter, navigate and analyze each explicitly. Keep their evidence separate.

Read the saved JSON with `read_file`. Present the website, scan date, browser,
and a table of technology, category, detected version (or unknown), and confidence.
Cite the scanned page. Describe these as automated detections; confidence is
Wappalyzer's heuristic score, not a calibrated probability. Include coverage limits,
page-loading problems and fallback reasons. Avoid inferring spend, revenue,
security vulnerabilities or complete infrastructure from detected technologies.
In capture mode, distinguish `basis=matched` from `basis=implied`. The stock CLI
also includes implied technologies but does not expose this distinction in its
output; describe its results as potentially inferred, especially backend databases.

## Pitfalls

- Upstream's stock CLI uses Puppeteer/Chromium; it cannot launch Camoufox.
  The capture helper reuses the same upstream engine and fingerprints without
  modifying them. It covers HTML, meta tags, text, inline scripts and script URLs,
  but not headers, cookies, JavaScript globals, DOM rules or DNS probes.
- Preserve capture JSON exactly. If browser output is truncated, save it through
  the browser tool's file/artifact mechanism or use CLI fallback; do not analyze
  an incomplete copy or hand-invent page data.
- An access-denied, login or challenge page is not the intended site's stack.
  Inspect the browser result before analysis; report blocks rather than treating
  challenge-page technologies as company technologies.
- No detections means no matching fingerprints in the collected signals, not
  proof that a technology is absent. The pinned database may miss newer tools.
- Upstream code and fingerprints retain their GPL-3.0 license. The skill helper
  and instructions are Apache-2.0. Upstream is neither bundled nor relicensed;
  do not interpret this integration as permission to redistribute upstream.

## Verification

Run `--check` to verify which checkout the skill resolves. For a local fixture,
serve HTML with a generator meta tag such as WordPress, open it in the
preferred browser and run capture analysis. Confirm that the report names the
technology, actual browser and capture limitations. Test CLI fallback against the
same local fixture when Chromium is installed. Research execution should work
without Git, npm, package installation or dependency downloads. Release artifacts
must contain only this integration, never the separately supplied detector.
