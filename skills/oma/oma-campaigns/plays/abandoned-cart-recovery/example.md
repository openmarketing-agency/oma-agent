# Example: Kestrel Supply

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Kestrel Supply sells technical outdoor apparel, such as rain shells, base layers and insulated jackets, on Shopify, with Klaviyo for email. Average order is about $140, and about 70% of carts are abandoned, with sizing the most common question to support. Shopify and Klaviyo are connected, and email consent is recorded at checkout. The only flow running is Shopify's default reminder.

## Why this idea
Ideas 132 (abandoned cart recovery), 133 (post-purchase cross-sell) and 134 (back-in-stock alerts). With carts left every day and no real flow, this is the fastest revenue the store can add.

## Campaign
```yaml
id: cart-recovery
name: Cart Recovery
description: Bring Kestrel Supply shoppers back to the gear they left in the cart.
orchestrator: cart-recovery__orchestrator
agents: [cart-recovery__orchestrator, cart-recovery__flow-writer, cart-recovery__merchandiser, cart-recovery__publisher]
integrations: [shopify]
integration_categories: [ecommerce]
goals:
  - Shoppers who abandon a cart come back and complete the order; track recovered orders and recovered revenue per flow, with targets after a two-week baseline.
plans:
  - "Ship the three-email cart flow with the abandoned items in stock in the shopper's size and a fit review."
  - "Add browse abandonment and a post-purchase layering cross-sell."
  - "Test two variants a month, starting with the sizing email, and keep the winners."
  - "Free shipping in email 3 only; no percentage discounts."
  - "Fit advice comes from the size guide, never guessed."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| cart-recovery__orchestrator | Next test picked with its hypothesis, plus a review note on recovery and revenue | file, web, skills, memory, session_search, kanban, integrations | emails, cro, analytics |
| cart-recovery__flow-writer | One finished email or variant with three subject lines, body, product block and call to action | file, web, skills, memory, kanban | emails, copywriting, marketing-psychology, writing-style-and-tone, humanizer |
| cart-recovery__merchandiser | Product, stock and size rules for one flow, plus cross-sell picks | file, web, skills, memory, kanban, integrations | offers |
| cart-recovery__publisher | Approved emails built in Klaviyo with consent and stop rules, test sends checked, flow switched on | file, web, skills, memory, kanban, integrations | emails |

## First week
- The cart flow's product rules and three emails.
- The flow built in Klaviyo, tested and switched on under the campaign's publication mode.
- A baseline of carts, recoveries and revenue for the last 30 days.
