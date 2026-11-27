# Example: Lantern Forge

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Lantern Forge is a four-person indie studio. Its game, Emberfall, is a co-op roguelike in early access on Steam for $19.99. The Discord server has 6,200 members; #help gets about 40 questions a day, many of them repeats about save sync, controller setup and unlocks. Questions sit unanswered for hours while the team ships patches. The studio's bot is in the server with posting rights in #help, #faq and #events.

## Why this idea
Idea 102 (Discord community). The audience is already in the server and asking; fast answers and a weekly reason to return keep players playing and talking about the game.

## Campaign
```yaml
id: discord
name: Discord
description: Answer Emberfall players fast in the server, keep a current FAQ, and run a weekly event.
orchestrator: discord__orchestrator
agents: [discord__orchestrator, discord__responder, discord__knowledge-keeper, discord__events-host, discord__publisher]
integrations: [discord]
integration_categories: ["team chat"]
goals:
  - Players get answers fast and come back weekly, and more of them wishlist the next update; track time to first answer, weekly returning members and event turnout, with targets after four weeks.
plans:
  - "Clear"
  - "Answer new questions daily and turn repeats into FAQ entries."
  - "Run a weekly event, such as the Friday seed challenge."
  - "Pass bug reports to the team the same day."
  - "Never promise release dates or features the studio hasn't announced."
  - "Bug reports go to the team in #bug-triage, not answered with guesses."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| discord__orchestrator | Open questions assigned, FAQ topics and event chosen, escalations flagged, review note | file, web, skills, memory, session_search, kanban, integrations | community-marketing, customer-research |
| discord__responder | Answer drafts for every assigned question, each linking its source | file, web, skills, memory, kanban | reply-and-comment-writer, writing-style-and-tone, humanizer |
| discord__knowledge-keeper | New FAQ entries for repeats, fixes for entries the patch broke | file, web, skills, memory, kanban | educational-content-and-how-to, copywriting, humanizer |
| discord__events-host | The week's event announcement, reminder, rules and last recap | file, web, skills, memory, kanban | events, community-marketing, writing-style-and-tone, humanizer |
| discord__publisher | Approved messages posted through the bot with links recorded | file, skills, memory, kanban, integrations | none |

## First week
- Every open question in #help answered, and ten FAQ entries pinned.
- The first Friday seed challenge announced, with reminder and recap.
