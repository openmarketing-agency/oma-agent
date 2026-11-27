# Example: Ortega & Lin Immigration Law

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Ortega & Lin is a three-attorney immigration firm in San Diego. It handles family-based green cards, naturalization and removal defense, with consultations at $150 in English and Spanish. A family case is worth about $4,500 in fees. The partners approved $3,000 a month for Google Search ads with a $100 daily cap. The site runs on WordPress and is connected; Google Ads and Google Analytics are connected and the booking form is tracked.

## Why this idea
Idea 146 (search ads on buying intent). People search for an immigration lawyer when they're ready to hire one, and a case pays for many clicks.

## Campaign
```yaml
id: search-ads
name: Search ads
description: Reach people in San Diego searching for an immigration lawyer and book paid consultations.
orchestrator: search-ads__orchestrator
agents: [search-ads__orchestrator, search-ads__keyword-planner, search-ads__ad-writer, search-ads__landing-page-writer, search-ads__publisher]
integrations: [googleads, google-analytics]
integration_categories: ["ads & conversion", analytics]
goals:
  - People in San Diego searching for an immigration lawyer book a $150 consultation at under $600 per booked case; track cost per booked consultation and per signed case, with targets after three weeks.
plans:
  - "Before dependent work, confirm the prerequisite: Budget approved for ads, with daily caps."
  - "Launch ad groups for marriage green cards, naturalization and removal defense, each with its own page in English and Spanish."
  - "Add negatives weekly, such as forms, free, USCIS and jobs."
  - "Move budget toward the ad group with the lowest cost per signed case."
  - "Add one ad group a week once the first three are judged."
  - "Ads promote legal advice and representation, never the government forms themselves; check Google's government documents policy before targeting visa searches."
  - "No guaranteed outcomes, approval rates or success claims; follow the State Bar of California's rules on lawyer advertising."
  - "Spend stays within $3,000 a month and $100 a day."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| search-ads__orchestrator | Spend against budget, cost per lead per ad group, changes proposed, review note | file, web, skills, memory, session_search, kanban, integrations | ads, conversion-tracking |
| search-ads__keyword-planner | Ad groups with keywords, match types, negatives and estimated cost per click | file, web, skills, memory, kanban, integrations | ads, audience-research |
| search-ads__ad-writer | Headlines, descriptions, sitelinks and callouts per ad group, claims checked | file, web, skills, memory, kanban | ad-creative, copywriting, humanizer |
| search-ads__landing-page-writer | A landing page per ad group with headline, proof, price and booking form | file, web, skills, memory, kanban | copywriting, cro, humanizer |
| search-ads__publisher | Approved changes applied and logged, pages published, tracking confirmed | file, skills, memory, kanban, integrations | none |

## First week
- Tracking confirmed on the booking form.
- Three ad groups live with six landing pages, English and Spanish.
- The first search terms report turned into negatives.
