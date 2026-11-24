# Example: Fernbloom

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Fernbloom is a direct-to-consumer skincare brand selling a three-step barrier-repair routine for sensitive skin, at $64 for the starter kit, on Shopify. Its Instagram business account has about 18,000 followers; carousels about ingredients get the most saves. Instagram and Shopify are connected. There is no email list beyond order emails.

## Why this idea
Ideas 69 (comment-to-DM giveaway), 67 (education carousels) and 71 (Instagram reply desk). The audience already saves ingredient carousels; a comment keyword turns that attention into conversations and sales.

## Campaign
```yaml
id: routine-finder
name: Routine Finder
description: Turn Fernbloom's ingredient carousels into DM conversations and starter-kit sales.
orchestrator: routine-finder__orchestrator
agents: [routine-finder__orchestrator, routine-finder__content-maker, routine-finder__dm-writer, routine-finder__publisher]
integrations: [instagram, shopify]
integration_categories: ["social media accounts", ecommerce]
goals:
  - Instagram followers with sensitive skin comment ROUTINE, get the free routine finder in their DMs, and buy the starter kit; track keyword comments, reply rate and orders with the DM code, with targets after three weeks.
plans:
  - "Publish the first carousel, \"5 ingredients that wreck a skin barrier\", with the routine finder PDF and its message set."
  - "Keep three keyword posts a week, alternating carousels and Reels."
  - "Reply privately to every ROUTINE comment and continue each conversation that answers."
  - "Repeat the formats and offers that turn comments into orders."
  - "No claims that the products treat eczema, rosacea or any condition."
  - "The DM code is FERN10, 10% off the starter kit only."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| routine-finder__orchestrator | Next three keyword posts planned, plus a review note on comments, replies and orders per post | file, web, skills, memory, session_search, kanban, integrations | social, offers, instagram-growth |
| routine-finder__content-maker | One keyword carousel with slide copy and image prompts, or a Reel script, with caption | file, web, skills, memory, kanban | carousel-writer, reels-script, caption-writer, hook-writer |
| routine-finder__dm-writer | The full message set for one post, plus the day's public comment replies | file, web, skills, memory, kanban | social-selling-and-dm, copywriting, writing-style-and-tone |
| routine-finder__publisher | Approved posts published, a private reply to every new ROUTINE comment, conversations needing a person flagged | file, web, skills, memory, kanban, integrations | reply-and-comment-writer |

## First week
- The routine finder PDF and three keyword posts, two carousels and one Reel.
- Message sets for all three.
- Scan for new ROUTINE comments hourly; prepare eligible replies only within the messaging window and send them through the approved publication workflow.
