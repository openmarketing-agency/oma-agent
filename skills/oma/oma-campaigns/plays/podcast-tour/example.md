# Example: Halden Advisory

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Halden Advisory is a three-person consulting firm that helps mid-size third-party logistics companies cut warehouse labor costs. The founder, Mara Halden, ran operations at two 3PLs for 15 years and has detailed stories about slotting, labor planning and peak season. Clients come from referrals; the firm has a website, a small blog and Mara's LinkedIn. Her mailbox and the blog are connected. She can record one podcast a week.

## Why this idea
Ideas 36 (podcast tour) and 30 (journalist source requests). Logistics buyers listen to niche supply-chain podcasts, and Mara's stories are the firm's best proof.

## Campaign
```yaml
id: podcast-tour
name: Podcast Tour
description: Put Mara Halden on the supply-chain podcasts 3PL operators listen to.
orchestrator: podcast-tour__orchestrator
agents: [podcast-tour__orchestrator, podcast-tour__show-researcher, podcast-tour__pitch-writer, podcast-tour__prep-writer, podcast-tour__publisher]
integrations: [gmail]
integration_categories: [email]
goals:
  - Mara appears on podcasts 3PL operations leaders listen to, and listeners book a discovery call; track bookings, episodes aired and discovery calls from episode links, with targets after four weeks.
plans:
  - "Send the first five pitches with Mara's guest sheet on peak-season labor planning, slotting and warehouse KPIs."
  - "Keep five new pitches a week, with one follow-up each."
  - "Prepare Mara for every booking and turn every aired episode into a recap post on the blog."
  - "Review weekly and pitch more shows like the ones that book."
  - "Client names only where the client has agreed in writing."
  - "Savings figures only from engagements Mara can describe in detail."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| podcast-tour__orchestrator | Pipeline updated, next shows approved, review note | file, web, skills, memory, session_search, kanban, integrations | public-relations |
| podcast-tour__show-researcher | Five qualified shows with host, audience, recent episodes, angle and contact | file, web, browser, skills, memory, kanban | public-relations, audience-research, podcast-and-audiograms |
| podcast-tour__pitch-writer | Five individual pitches, plus guest sheet updates | file, web, skills, memory, kanban | public-relations, cold-email, copywriting, writing-style-and-tone |
| podcast-tour__prep-writer | A prep brief per booking; a recap post and snippets per aired episode | file, web, skills, memory, kanban | podcast-and-audiograms, copywriting, educational-content-and-how-to, writing-style-and-tone |
| podcast-tour__publisher | Approved pitches sent from Mara's mailbox, bookings handed to her, recaps published | file, web, skills, memory, kanban, integrations | none |

## First week
- The guest sheet with three topics and a bio.
- Five researched shows and five pitches, sent after approval.
