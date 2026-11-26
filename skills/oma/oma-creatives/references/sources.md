# Sources Template

Save as `<target-root>/sources.yaml` before collecting. For `own`, `collect.py sources` writes it; review it and add verified profiles it could not know about. For a competitor or reference, write it from the target's `profile.md` and `gtm.md`.

```yaml
target: deckly                       # "own" or the competitor/reference id
name: Deckly                         # the advertiser name exactly as the brand writes it
website: https://deckly.example/
socials:                             # verified first-party profiles only; omit unknown platforms
  instagram: https://www.instagram.com/deckly/
  tiktok: https://www.tiktok.com/@deckly
  facebook: https://www.facebook.com/deckly
  x: https://x.com/deckly
  linkedin: https://www.linkedin.com/company/deckly/
  youtube: https://www.youtube.com/@deckly
  pinterest: https://www.pinterest.com/deckly/
  threads: https://www.threads.com/@deckly
  bluesky: https://bsky.app/profile/deckly.example
  reddit: https://www.reddit.com/user/deckly
unsupported: [discord]               # verified profiles on platforms without a collector
ads:
  meta: {page_url: "https://www.facebook.com/deckly", advertiser: Deckly}   # or {page_id: "123"} or {query: Deckly, advertiser: Deckly}
  google: {domain: deckly.example}                                          # or {advertiser_id: AR0123...}
  linkedin: {company_url: "https://www.linkedin.com/company/deckly/", advertiser: Deckly}   # or {company_id: "2850862"}
  tiktok: {advertiser: Deckly}                                              # optional: countries: [DE, FR]
```

- Every library key is required. Set a library to `{skip: "reason"}` only when it clearly does not fit (for example LinkedIn for a consumer storefront); the collector records it as `not_checked` with that reason.
- Prefer exact identifiers: a Facebook page URL or ID over a keyword, a LinkedIn company page over a name. A keyword search matches other advertisers' ad text and can only be filtered by name.
- A profile you could not verify stays out of `socials`; say so in `creatives.md` Coverage instead of guessing a handle.
