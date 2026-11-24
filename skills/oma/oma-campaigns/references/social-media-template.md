# Social media campaign template

Use when the playbook prioritizes reaching or responding to an audience on social channels. Choose the audience, intended brand accounts, interactions in scope, and outcome for each channel. Use the platforms the user named or that the saved brand and playbook clearly support; ask only if the choice is unclear.

## Example campaign config

This example uses LinkedIn for posts and public conversations, GA4 for tracked sign-ups, and HeyGen for presenter videos. Replace the integrations with the specific channels, measurement, and media tools in scope.

```yaml
id: social-media
name: Social Media
description: Build relevant conversations and drive qualified visits from social.
orchestrator: social-media__orchestrator
agents:
  - social-media__orchestrator
  - social-media__content-creator
  - social-media__publisher
integrations: [linkedin, google-analytics, heygen]
goals:
  - Increase substantive conversations with the target audience and qualified sign-ups from tracked social links.
plans:
  - Baseline engagement and referral sign-ups on the verified accounts; pick a small set of themes tied to audience questions.
  - Draft channel-native posts and useful replies, and prepare approved presenter clips where useful; have the publisher apply authorized revisions on the intended account.
  - Review new conversations and referral outcomes, then refine themes, formats, and response priorities instead of optimizing for impressions alone.
```

- **Team:** Keep the orchestrator and publisher. Add a content creator if posts and replies need separate drafting. The publisher verifies the destination and records the live post or reply ID.
- **Review:** A 30-minute activity check may be warranted when timely replies matter and access, rate limits, and cost support it. Use a slower separate review for content performance, for example twice weekly. Check new comments, replies, mentions, tags, and relevant threads; include inbox messages only if authorized and in scope.

For the 30-minute job declaration, load the social media orchestrator example with `skill_view` (`name: oma-agents`, `file_path: references/social-media-orchestrator-template.md`). Adapt the account and read tools to the campaign's verified access.

For the matching `social-media__content-creator`, load `references/social-media-content-writer-template.md` from `oma-agents`.

## Campaign integrations

Save the selected platform IDs in `integrations` in the campaign's `config.yaml` before asking the user to connect any missing accounts in the OMA console. Do not ask for MCP configuration or credentials in chat. Leave the campaign paused (or a draft) and its jobs unscheduled until the required accounts and permissions are verified. Follow the [integration intake guide](integration-intake.md).

The example uses `heygen` for presenter videos. Omit it if the plan does not need generated media, or consider `higgsfield` or `runway` instead for visuals or motion.
