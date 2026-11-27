# Example: Driftless

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Driftless is an open-source, Apache 2.0 command-line tool that detects and fixes schema drift between Postgres environments. It has about 1,200 GitHub stars, docs on its own site, and a small Discord. Version 1.0 adds a browser playground that runs against a sample database with no signup. The maker, Priya Nair, works on it full time and can be online all launch day. GitHub and the docs site are connected; there is no Hacker News launch on record.

## Why this idea
Ideas 111 (Show HN), 116 (open-source launch) and 110 (launch-worthiness review). The 1.0 playground is something strangers can try today, which is what Show HN is for.

## Campaign
```yaml
id: launch-1-0
name: 1.0 Launch
description: Launch Driftless 1.0 to Postgres developers with a playground they can try without signing up.
orchestrator: launch-1-0__orchestrator
agents: [launch-1-0__orchestrator, launch-1-0__launch-writer, launch-1-0__demo-builder, launch-1-0__publisher]
integrations: [github, x, linkedin]
integration_categories: ["developer tools", "social media accounts"]
goals:
  - Postgres developers try the 1.0 playground on launch day and run their first drift check within 14 days; track playground sessions, installs and first successful checks, with targets set after launch week.
plans:
  - "Ship a quickstart verified in a fresh container and a README rebuilt around it."
  - "Record the playground demo, write the 1.0 release notes and the Show HN fact sheet."
  - "Launch when the checklist passes; Priya posts the Show HN and answers every comment."
  - "Within a week, ship the fixes comments asked for, publish a recap and open good-first-issues."
  - "Benchmarks only from runs the demo-builder reproduced."
  - "Don't mention the hosted version on the roadmap."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| launch-1-0__orchestrator | Readiness checklist updated with blockers and owners, next assets queued | file, web, skills, memory, session_search, kanban, integrations | launch, analytics |
| launch-1-0__launch-writer | One finished asset per task: README, release notes, fact sheet, launch post or recap | file, web, skills, memory, kanban | launch, copywriting, educational-content-and-how-to, writing-style-and-tone, humanizer |
| launch-1-0__demo-builder | One runnable demo: quickstart verified in a fresh container, recording script or sample repo | file, terminal, web, skills, memory, kanban | educational-content-and-how-to |
| launch-1-0__publisher | Approved GitHub and site changes shipped with URLs; fact sheet handed to Priya; thread URL recorded | file, web, skills, memory, kanban, integrations | none |

## First week
- The quickstart runs in a fresh container, with two broken steps fixed in the docs.
- A new README in a pull request, ready for approval.
- The readiness checklist with the launch date and three open blockers.
