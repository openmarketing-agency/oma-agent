# B2B SaaS brand template

Use for a website-led software business. The names, URLs, and findings below are fictional. Replace them with first-party evidence and confirmed user input; do not carry example statuses into a real record.

## `config.yaml`

```yaml
id: relaydesk
name: RelayDesk
description: Client onboarding workflow software for small agencies.
website:
  status: verified
  url: https://relaydesk.example/
channels:
  blog:
    status: verified
    url: https://relaydesk.example/blog
  newsletter:
    status: not_checked
integrations:
  google_analytics:
    status: observed
    signal: A GA4 event request appeared on the public product page.
    evidence: research/website-integrations.md
knowledge_base_file: knowledge-base.md
```

## `knowledge-base.md`

```markdown
# RelayDesk brand knowledge

- Audience: The [product page](https://relaydesk.example/product) positions RelayDesk for operations leads at small agencies coordinating client onboarding.
- Product: The [workflow guide](https://relaydesk.example/help/workflows) shows task owners, handoff dates, and status. It does not substantiate claims about time or money saved.
- Conversion: The [pricing page](https://relaydesk.example/pricing) points to a trial signup. The signed-in onboarding path and successful first workflow were not checked.
- Open questions: Confirm the first buyer segment, approved customer proof, and who can authorize read-only funnel reporting.
```

For the integration example, `research/website-integrations.md` would record the checked URL and time, the provider request that was observed during a normal page load, and what was not checked. Write that report before referencing it. A public tag or request does not verify property ownership, reliable reporting, or account access. Omit the integration entry if you have no evidence to classify it.
