# Example: Tallybook

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Tallybook does bookkeeping and tax filing for US freelancers and creators, for a flat $79 a month. Its founder, Jordan Reyes, is a CPA who answers questions on Reddit now and then. Freelancers regularly ask in subreddits like r/freelance and r/tax, and on X, about quarterly taxes, deductions and whether they need an accountant. The blog runs on Ghost and is connected; Reddit and X are read through search. Jordan can post replies four days a week.

## Why this idea
Ideas 2 (buying-intent listening), 99 (Reddit community answers) and 16 (Reddit questions into articles). The people Tallybook serves ask for help in public every day.

## Campaign
```yaml
id: listening
name: Listening
description: Answer freelancers' tax questions where they ask them, and turn the common ones into answer pages.
orchestrator: listening__orchestrator
agents: [listening__orchestrator, listening__scout, listening__responder, listening__answer-writer, listening__publisher]
integrations: [wordpress-com, google-analytics]
integration_categories: ["content & files", analytics, "social media accounts"]
goals:
  - Freelancers asking tax questions get a useful answer from Jordan and book a free consult; track replies posted, referral visits and consults that name a community or answer page, with targets after four weeks.
plans:
  - "Post the first five replies and publish \"Quarterly taxes for freelancers, explained\"."
  - "Keep ten replies a week within each community's rules, and one answer page a week."
  - "Link replies to answer pages where the venue allows links."
  - "Focus on the communities whose threads lead to consults."
  - "General information only; say when someone needs advice on their own situation."
  - "Tax figures and dates link to the IRS page they come from."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| listening__orchestrator | The day's picked threads assigned, next answer page chosen, review note | file, web, skills, memory, session_search, kanban, integrations | community-marketing, customer-research |
| listening__scout | Up to 15 new threads with link, venue rules, age, need and fit | file, web, browser, skills, memory, kanban | reddit-marketing, audience-research |
| listening__responder | A reply draft for every picked thread, useful on its own, disclosed | file, web, skills, memory, kanban | reply-and-comment-writer, reddit-marketing, writing-style-and-tone |
| listening__answer-writer | One answer page per task with the full answer and examples | file, web, skills, memory, kanban | educational-content-and-how-to, copywriting, writing-style-and-tone |
| listening__publisher | Approved replies handed to Jordan with posted URLs recorded; answer pages published | file, web, skills, memory, kanban, integrations | none |

## First week
- 15 recorded threads and five reply drafts that Jordan posts.
- The first answer page, on quarterly taxes, published.
