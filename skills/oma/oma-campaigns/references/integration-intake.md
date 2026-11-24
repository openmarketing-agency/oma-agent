# Campaign integration intake

Choose integrations from the canonical OMA catalog, not a generic list of tools. The source catalog ships as `hermes_cli/oma_campaigns/schemas/integrations.json`; use the workspace's integrations catalog when available. The campaign launcher's `integrations` command only suggests candidates from brand evidence, so a service that isn't detected on the website can still be a valid catalog choice.

## Save the integrations before requesting a connection

1. Identify the action, the role that must perform it, and the account or project it needs. Use the user's selected platforms or the clear choice from the saved brand and playbook. Prefer suitable existing connections. If a required platform is still unclear, ask only which supported platform to use. Do not request a connector for optional work the user deferred.
2. Write the canonical IDs to `integrations: [...]` in `oma/campaigns/<campaign_id>/config.yaml` before asking the user to connect anything. Include required platforms whose accounts are not yet connected. Do not add vendor names to `agent.enabled_toolsets`, add `integrations` to an agent record, or assume `oma_skills` installs a connection.
3. Have `default` direct the user to the campaign's integration setup in the OMA console. Group the missing connections in one message and name the provider, intended account, and required access where known. Ask the user to connect the accounts there, not to paste MCP configuration, server URLs, headers, API keys, tokens, or other credentials in chat. Do not write those values into campaign or agent records or set up ad hoc MCP servers instead.
4. Verify that the owning profile has the relevant tools and the needed access to the intended account. A public URL, catalog listing, or saved integration ID does not establish access. Until all required connections are verified, report what is missing and leave the campaign in draft or paused. You may prepare local drafts, but do not start or resume the campaign, dispatch campaign work, or register or enable jobs.

## Media generation examples

| Approved deliverable | Catalog candidates to verify |
| --- | --- |
| Original hero image, social graphic, or generated visual | `higgsfield`, `fal-ai`, or `replicate`, depending on the needed operation and the available connector. |
| Product clip, motion asset, or b-roll | `runway` or `higgsfield`, depending on the requested output. |
| Presenter or avatar video | `heygen`; confirm consent, rights, and disclosure requirements for the selected likeness or voice. |

These IDs are options, not defaults. `higgsfield` and `higgsfield-mcp` are distinct catalog entries; select the one that matches the actual connection. Verify supported media operations, approved assets, and any cost constraints before generation. Keep drafts and media handoffs separate from authority to publish.

Example after saving `integrations: [linkedin, instagram]`: **“I saved the campaign with LinkedIn and Instagram. Please connect the brand's Instagram account in the OMA console. The campaign will stay paused until that connection is verified.”** This assumes LinkedIn access is already verified.
