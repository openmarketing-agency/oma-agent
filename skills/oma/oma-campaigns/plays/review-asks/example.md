# Example: Riverside Family Dental

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Riverside Family Dental runs two clinics in Portland, Oregon, with six dentists, focused on families and nervous patients. Each clinic has a Google Business Profile with about 80 reviews, rated 4.6, and many reviews from last year have no reply. Patients book online or by phone. The practice management system exports last week's patients with their email consent, and that export and both profiles are connected.

## Why this idea
Ideas 144 (review asks and replies) and 143 (Google Business weekly posts). Families choose dentists from the map results, by rating and recent reviews.

## Campaign
```yaml
id: reviews
name: Reviews
description: Grow honest Google reviews for both Riverside clinics and reply to every one.
orchestrator: reviews__orchestrator
agents: [reviews__orchestrator, reviews__request-writer, reviews__reply-writer, reviews__post-writer, reviews__publisher]
integrations: [google-business-profile]
integration_categories: [marketing]
goals:
  - More patients leave honest Google reviews and more nearby families book; track new reviews per week, rating, and calls and bookings from the profiles, with targets after four weeks.
plans:
  - "Before dependent work, confirm the prerequisite: Weekly export of last week's patients with email consent."
  - "Reply to the 34 unanswered reviews from the last year and publish the first profile post for each clinic."
  - "Every Monday, send requests to every patient seen the week before, with one reminder."
  - "Reply to every new review within two business days, and post weekly on each profile."
  - "Send the owners a monthly summary of recurring themes in reviews."
  - "Replies never confirm that the reviewer is a patient or mention any visit or treatment."
  - "Posts show staff only with their written consent on file."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| reviews__orchestrator | Last week's cohort defined, the batch queued, a review note on new reviews and themes | file, web, skills, memory, session_search, kanban, integrations | social-proof-and-testimonials |
| reviews__request-writer | The week's batch: one request per patient and reminders for non-responders | file, web, skills, memory, kanban, integrations | emails, copywriting, humanizer |
| reviews__reply-writer | A reply draft for every new review; negative ones flagged to the owners | file, web, skills, memory, kanban | reply-and-comment-writer, crisis-and-moderation, writing-style-and-tone, humanizer |
| reviews__post-writer | One post per clinic with text, photo brief and booking button | file, web, skills, memory, kanban | copywriting, humanizer |
| reviews__publisher | Approved requests sent, replies and posts published, each logged | file, web, skills, memory, kanban, integrations | none |

## First week
- 34 reply drafts for last year's unanswered reviews.
- Request and reminder templates approved, and the first batch sent.
- One post on each clinic's profile.
