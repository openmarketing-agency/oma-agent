# Presenton playbook example

This is a worked example of the depth and structure of a complete playbook. It illustrates one positioning statement serving several overlapping audiences, with a distinct job for each channel. Use the structure for other brands, not Presenton's product claims, audiences, or channel choices. Check product claims against current evidence before using them externally.

```yaml
id: marketing-strategy
name: Presenton Marketing Strategy
description: Overall marketing direction for Presenton, covering who we serve, what we stand for, what each channel does and how we measure progress.
strategy: |-
  What Presenton is
  Presenton is the open-source AI presentation engine you can run anywhere. It turns prompts,
  documents and data into editable PowerPoint decks (and PDFs) in your own brand, using the AI
  model you choose, on cloud, desktop or your own servers, including fully air-gapped.

  Positioning
  The AI presentation tool you control. Most AI presentation tools are closed, cloud-only SaaS.
  Presenton gives you:
  - Control: self-host or run air-gapped, bring any model (OpenAI, Anthropic, Gemini, local or
    OpenAI-compatible), and keep your data with you.
  - Real files: editable PPTX, not a web page you can't take with you.
  - Your brand: your own templates, brand rules and asset library.
  - Automation: API and MCP for decks and reports that repeat.
  - Open source: free to start, transparent, built with the community.
  Lead with control and editable output. They are the clearest differences.

  Who we market to
  Three audiences that feed each other:
  1. Organizations that can't send documents to third-party AI (banks, government, telecom,
     consulting, regulated industries). They bring revenue. Talk to IT and AI platform teams,
     and to the teams that make decks every week, about privacy, brand compliance and deployment.
  2. Developers and AI builders automating decks and reports through the API, MCP, n8n or agents.
     They bring usage and integrations, and often bring Presenton into their companies.
  3. Open-source users, self-hosters and local-LLM fans who want a free, private alternative.
     They bring reach, GitHub momentum, feedback and word of mouth.
  The brand story stays broad: "AI presentations you control". Tailor the angle to each
  audience, but don't narrow the brand down to just one of them.

  What success looks like
  - Presenton is the default answer when someone looks for an open-source, self-hosted or
    private AI presentation tool.
  - That attention turns into usage: installs, downloads, signups, first exported deck, API calls.
  - Usage turns into revenue: enterprise inquiries, booked calls, pilots and paid plans.

  Channels and their roles
  - Website, blog and SEO: capture search intent (private or self-hosted AI presentations,
    open-source alternatives, presentation and PPTX APIs, on-brand template automation).
    Improve existing pages and compare pages before writing new ones.
  - GitHub: the front door for technical users. Keep the README, demos and release notes sharp.
    Every release is a marketing moment.
  - Communities (Reddit, Hacker News, Discord, self-hosting and local-LLM forums): be useful,
    answer questions, share real builds. Founder voice, casual, never salesy.
  - X: build in public, releases and demos for the developer and open-source crowd.
  - LinkedIn: founder-led posts for enterprise buyers on private AI, data sovereignty,
    brand-compliant decks and deployment stories.
  - Video (YouTube, short demos): show the real product: setup, local models, templates, API.
  - Integrations and directories: get listed where builders already look (MCP registries,
    automation templates, AI tool directories, cloud marketplaces).
  - Lifecycle email: help signups reach their first good deck, and route users who show
    enterprise intent to a call.
  - Launches (Product Hunt and similar): only for major releases.
  The base layer runs all the time: SEO, GitHub and communities. Amplifiers carry each release
  and proof point: X, LinkedIn, video and launches. Newsletter and paid ads come later, once a
  channel proves it converts.

  What we talk about
  - Private AI for business documents, and how to run it on your own models and hardware.
  - Editable, on-brand decks from your own templates.
  - Automating recurring decks and reports, with real workflows.
  - Building in the open: releases, roadmap, community contributions.
  - Proof: deployments, customer stories (with permission), model benchmarks.

  Voice
  Technical, plain and honest. Show the product working instead of describing it. Be fair to
  competitors. In communities, write like a person, not a brand.

  Measuring progress
  Judge each channel by what it moves further down the funnel, not by how much it produces.
  - Reach: search impressions and clicks, GitHub stars and traffic, social reach, mentions.
  - Usage: installs, downloads, signups, first exported deck, API usage.
  - Revenue: enterprise inquiries, booked calls, pilots, paid conversions.
  Record the source of every booked call and pilot. Put more effort into channels that drive
  usage and revenue, and cut the ones that only add noise. When data is missing, say so
  instead of guessing.

  Claims
  Only claim what the current release actually does. Don't claim certifications we don't
  hold (for example SOC 2). Comparisons use current sources and acknowledge tradeoffs.

  Revisit this direction when the product, pricing or target audience changes. Week-to-week
  decisions belong to the campaigns.
```
