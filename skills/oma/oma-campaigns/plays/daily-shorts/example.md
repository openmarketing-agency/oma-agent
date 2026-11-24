# Example: Repwise

A made-up business, to show the play producing real work. Don't copy its details into a real campaign.

## Business
Repwise is an iOS and Android app that builds strength programs and adjusts them after each workout, for $12.99 a month with a 7-day trial. Users are mostly beginners aged 25 to 40 training at home or in commercial gyms. The YouTube channel has about 2,000 subscribers and a few long tutorials; comments ask questions like "how many sets should a beginner do?". YouTube is connected, and app installs are tracked per link.

## Why this idea
Ideas 89 (daily Shorts) and 86 (search-first tutorials). Beginners search YouTube with exactly the questions the app answers, and the app's adjusted-plan screen is easy to show on camera.

## Campaign
```yaml
id: shorts
name: Shorts
description: Answer beginner strength questions in a daily Short that shows Repwise doing the planning.
orchestrator: shorts__orchestrator
agents: [shorts__orchestrator, shorts__idea-scout, shorts__scriptwriter, shorts__producer, shorts__publisher]
integrations: [youtube]
integration_categories: ["video & audio"]
goals:
  - Beginners searching strength questions find Repwise through Shorts and start a trial; track average view duration, link clicks and trials from the Shorts link, with targets after three weeks.
plans:
  - "Reuse app-onboarding's screen-recordings before starting dependent work."
  - "Publish the first three Shorts, starting with \"How many sets should a beginner do?\", answered with the app's plan screen."
  - "Keep one Short a day across answer, myth versus fact, and plan-builder formats."
  - "Judge each format after five to eight videos, and repeat the ones that drive trials."
  - "No claims about weight loss amounts or medical outcomes."
  - "Exercise form shown only from the app's verified demo clips."
```

## Team
| Agent | Per run | Toolsets | Skills |
|---|---|---|---|
| shorts__orchestrator | Next week's seven videos assigned to formats, review note on retention and trials | file, web, skills, memory, session_search, kanban, integrations | goals-and-kpis, content-calendar |
| shorts__idea-scout | Seven ideas, each with its source question, hook and format | file, web, browser, skills, memory, kanban | trend-jacking, audience-research, content-research-and-sourcing |
| shorts__scriptwriter | Seven scripts with two hooks, beats, on-screen text, shot list, caption and title | file, web, skills, memory, kanban | short-form-video-script, hook-writer, caption-writer |
| shorts__producer | One finished 9:16 video per script with captions and a thumbnail frame | file, terminal, web, skills, memory, kanban | captions-and-clipping, ai-video, ai-voiceover, thumbnail-design |
| shorts__publisher | Approved videos uploaded with title, description, disclosures and tracked link, URLs recorded | file, web, skills, memory, kanban, integrations | none |

## First week
- Seven ideas from comments and search suggestions, and seven scripts.
- Three finished Shorts, published after approval.
