# Website integration research

## Collect evidence before assigning a status

1. Use verified public pages for the brand (homepage and relevant product, pricing, signup, or contact entry points). Follow the official website from the repository when the seed is GitHub. Record which URLs, redirects, date, and methods were checked. Inspect markup, then the relevant **deployed scripts** as text. Look for provider-specific loader URLs, initialization, verification tags, or documented first-party proxies; a generic keyword, an unused dependency, or a docs link is not enough.
2. When a browser is available, use `browser_exec` to load representative public pages normally. Inspect rendered widgets and resource requests (for example, `performance.getEntriesByType('resource')`); record provider host and path, not query strings, headers, payloads, session IDs, or event data. Use normal consent choices only when authorized. Do not log in, bypass consent or challenges, trigger conversions, replay requests, submit forms, or buy anything. Note geographic, consent, paywall, and route limits; server-side tracking may not be visible at all.
3. Save the scope and a dated evidence table in `research/website-integrations.md`. Distinguish **deployed configuration**, **request observed**, and **widget or verification marker observed**. Never infer delivery success, active account access, spend, spend attribution, or every downstream destination from a tag or request. Put repository-only evidence in the repository report, not in public website findings. Keep durable source links and redact identifiers and private data that are not needed to substantiate the observation.
4. In `config.yaml`, key `integrations` by stable lowercase snake_case provider IDs. Set `observed` only for specific public evidence, and link `evidence` to the report (optionally with an anchor). Set `not_detected` only when applicable checks were completed for a stated scope and no signal appeared; it is not proof of site-wide absence. If only HTML was inspected and the missing signal requires rendered, runtime, authenticated, or server-side evidence, use `not_checked` and explain the gap. Do not erase an earlier verified observation because a limited refresh was quiet; record the change in evidence and scope first. Account capabilities belong in the separate connected-source refresh report, never in `integrations`.

## Coverage checklist

Use the categories relevant to the brand. Prioritize providers actually evidenced on the site over speculative inventories.

| Category | Look for | What the finding is useful for |
| --- | --- | --- |
| Analytics | Google Analytics (GA4), Mixpanel, PostHog, Plausible, Amplitude, Umami, Fathom, Matomo | Find measurement and funnel baselines; verify property access and event definitions before using numbers. |
| Tag management | Google Tag Manager, server-side GTM, Stape | Identify the likely instrumentation workflow. A first-party tag endpoint alone does not identify its operator; edits require separate authorization. |
| Ads and pixels | Meta Pixel/Facebook Ads, AdSense, Google Ads, TikTok, LinkedIn, X, Reddit, Pinterest, Snap, Microsoft Ads | Flag candidate channels and conversion instrumentation. A pixel does not prove active campaigns or ad spend. |
| Revenue and commerce | Stripe, Paddle, Lemon Squeezy, Shopify, WooCommerce | Locate checkout and possible revenue-data sources; CAC and ROAS need separately verified spend, revenue, and attribution. |
| Customer data platforms | Segment, RudderStack | Identify a possible event collection hub. Do not infer enabled downstream destinations. |
| Search and SEO | Google Search Console, Bing Webmaster Tools, Ahrefs | Find search or site-verification signals; a marker does not establish access to a search property. |
| Email and SMS | Klaviyo, Mailchimp, Brevo, Kit, Loops, beehiiv, Customer.io | Identify potential newsletter and lifecycle tooling. Do not subscribe or collect subscriber data. |
| CRM | HubSpot, Pipedrive, Salesforce, ActiveCampaign | Identify potential lead and pipeline sources; distinguish an embed from actual CRM access. |
| Session replay | Microsoft Clarity, Hotjar, FullStory, LogRocket | Surface possible UX research tools; do not collect or export individual recordings. |
| Conversion and support | Calendly, Cal.com, Typeform, Tally, Intercom, Crisp | Map booking, forms, and support entry points without submitting them or collecting chat logs. |
| Reviews | Trustpilot, G2, Capterra, Judge.me, Yotpo | Find verified listings and recurring feedback; a badge is not account access. |
| Affiliate and partner | Rewardful, FirstPromoter, PartnerStack, Dub | Identify potential partner programs; a redirect or library alone does not prove an active program. |
| Error monitoring | Sentry and other evidenced providers | Distinguish deployed monitoring configuration from event delivery; do not induce errors to test it. |
