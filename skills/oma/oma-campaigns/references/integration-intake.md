# Campaign integration intake

Choose integrations from the canonical OMA catalog, not a generic list of tools. The source catalog ships as `hermes_cli/oma_campaigns/schemas/integrations.json`; use the workspace's integrations catalog when available. The campaign launcher's `integrations` command only suggests candidates from brand evidence, so a service that isn't detected on the website can still be a valid catalog choice.

## Ask for the connections the plan needs

1. Identify the action, the role that must perform it, and the account or project it needs: for example, CMS publishing, social reads, analytics, image generation, or video generation. Prefer already connected, suitable integrations and verify the owning profile's access. A public URL, catalog listing, skill ID, or saved integration declaration does not establish access.
2. If a required connection is missing, have `default` ask the user to connect it through the workspace's supported connection setup. Use `clarify` when available, otherwise ask in chat. Group missing connections in one question where practical. Name the provider, the deliverable it unblocks, and the scope needed. If several providers fit and no preference or suitable connection is known, offer a short list and ask for one. Do not ask for keys or tokens in chat.
3. Record the selected canonical IDs in the owning campaign's `integrations` list. Set up connector access separately in the intended profile using the supported configuration path. Do not add vendor names to `agent.enabled_toolsets`, add an `integrations` field to an agent record, or assume `oma_skills` installs an integration. Verify that the profile can discover the relevant tool and access the intended account before treating it as usable.
4. Record unresolved requirements as setup blockers and follow the campaign's activation check. Continue drafting or other authorized work that doesn't depend on the missing integration. Do not request a connector for optional work the user deferred.

## Media generation examples

| Approved deliverable | Catalog candidates to verify |
| --- | --- |
| Original hero image, social graphic, or generated visual | `higgsfield`, `fal-ai`, or `replicate`, depending on the needed operation and the available connector. |
| Product clip, motion asset, or b-roll | `runway` or `higgsfield`, depending on the requested output. |
| Presenter or avatar video | `heygen`; confirm consent, rights, and disclosure requirements for the selected likeness or voice. |

These IDs are options, not defaults. `higgsfield` and `higgsfield-mcp` are distinct catalog entries; select the one that matches the actual connection. Verify supported media operations, approved assets, and any cost constraints before generation. Keep drafts and media handoffs separate from authority to publish.

Example intake question: **“The launch needs a short product clip. Do you already have a Runway or Higgsfield connection you want us to use, or should we leave video out of this draft?”** If only one provider meets a required capability, ask for that connection instead of offering a false choice.
