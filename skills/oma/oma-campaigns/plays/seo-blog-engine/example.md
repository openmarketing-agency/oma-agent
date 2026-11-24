# Example: Ledgerline

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Ledgerline sells payroll and HR software to US companies with 20 to 200 employees, at $8 per employee per month with a 30-day free trial. Buyers are office managers and founders who outgrew spreadsheets or are leaving Gusto or ADP. The blog runs on WordPress, which is connected, as are Search Console and GA4. The blog has 40 posts, mostly product news, and gets little search traffic. People search for things like "how to run payroll for the first time", "payroll for 50 employees" and "Gusto alternatives".

## Why this idea
Ideas 8 (SEO blog engine), 11 (alternatives and vs pages), 15 (pillar guides) and 18 (rank-drop rescue). The playbook's priority is turning search into trials, and the research shows clear demand and weak existing content.

## Campaign
```yaml
id: search
name: Search
description: Turn payroll searches from small-business owners into Ledgerline trials.
orchestrator: search__orchestrator
agents: [search__orchestrator, search__researcher, search__writer, search__publisher]
integrations: [google-search-console, google-analytics, wordpress-com]
integration_categories: [analytics, "content & files"]
goals:
  - Office managers and founders at 20 to 200 person US companies find Ledgerline through non-brand search and start a trial; track non-brand clicks and organic trials, with targets after a four-week baseline.
plans:
  - "Reuse customer-proof's payroll-time-study before starting dependent work."
  - "Publish \"How to run payroll for the first time\" and \"Gusto alternatives for growing teams\" from the keyword map built at creation."
  - "Then two articles a week across the first-payroll, compliance and switching clusters, one comparison page a month, and two refreshes a month."
  - "Build a pillar guide on running payroll in-house once the first-payroll cluster has five articles."
  - "Review weekly over 28-day windows and shift effort to clusters gaining impressions."
  - "No tax or legal advice beyond what the IRS and state sites say; link the official source."
  - "Pricing claims match the live pricing page."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| search__orchestrator | Next week's two topics and any refresh, queued as tasks, plus a five-line review note | file, web, skills, memory, session_search, kanban, integrations | content-strategy, seo-audit |
| search__researcher | One brief per task: query, intent, what the top five miss, outline, sources, links, call to action | file, web, browser, skills, memory, kanban, integrations | seo-audit, competitors, ai-seo, programmatic-seo |
| search__writer | One finished draft: a 1,500 to 2,500 word article, a comparison page or a marked-up refresh | file, web, skills, memory, kanban | copywriting, copy-editing, competitors, writing-style-and-tone |
| search__publisher | Every approved draft live in WordPress with meta, schema and links, indexing requested, URL recorded | file, web, skills, memory, kanban, integrations | schema |

## First week
- Two briefs and two drafts: the first-payroll guide and the Gusto alternatives page.
- Both published after approval, with indexing requested.
- A Search Console baseline for the last three months, attached to the first review.
