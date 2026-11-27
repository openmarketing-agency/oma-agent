# Example: Tallybook

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Tallybook does bookkeeping and tax filing for US freelancers and creators, for a flat $79 a month. Its founder, Jordan Reyes, is a CPA. Freelancers ask in communities and on X about quarterly taxes, deductions and whether they need an accountant. In this example, Tallybook has a connected Reddit app authorized for this use and verified venues allow its replies. X is read through search; Jordan handles permitted replies there when the publisher can't send them. The blog is connected.

## Why this idea
Ideas 2 (buying-intent listening), 99 (Reddit community answers) and 16 (Reddit questions into articles). The people Tallybook serves ask for help in public every day.

## Campaign
```yaml
id: listening
name: Listening
description: Answer freelancers' tax questions where they ask them, and turn the common ones into answer pages.
orchestrator: listening__orchestrator
agents: [listening__orchestrator, listening__scout, listening__responder, listening__answer-writer, listening__publisher]
integrations: [wordpress-com, google-analytics, reddit]
integration_categories: ["content & files", analytics, "social media accounts"]
goals:
  - Freelancers asking tax questions get a useful answer from Tallybook and book a free consult; track replies posted, referral visits and consults that name a community or answer page, with targets after four weeks.
plans:
  - Use the authorized Reddit app for permitted replies, and hand off replies when the connector cannot act and the venue permits a person to post.
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
| listening__responder | A reply draft for every picked thread, useful on its own, disclosed | file, web, skills, memory, kanban | reply-and-comment-writer, reddit-marketing, writing-style-and-tone, humanizer |
| listening__answer-writer | One answer page per task with the full answer and examples | file, web, skills, memory, kanban | educational-content-and-how-to, copywriting, writing-style-and-tone, humanizer |
| listening__publisher | Permitted Reddit replies and answer pages published with URLs recorded; permitted manual fallback handed to Jordan | file, web, skills, memory, kanban, integrations | none |

## First week
- 15 recorded threads and five replies across eligible venues, with live URLs recorded.
- The first answer page, on quarterly taxes, published.
