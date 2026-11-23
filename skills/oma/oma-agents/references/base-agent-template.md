# Base OMA agent template

Use this reference to draft an agent record, not to replace the built-in `default` or `maintenance` profiles. Give the agent one clear responsibility and save `config.yaml`, `SOUL.md`, and `saves/` together under `oma/agents/<id>/` in the default Hermes home.

## `config.yaml`

This example is a campaign specialist. Replace the identity and description with the role's actual responsibility. The example omits a model and reasoning override so the role inherits the campaign's saved settings at provisioning or sync.

```yaml
id: seo__researcher
name: SEO Researcher
description: Finds and prioritizes evidence-backed organic search opportunities.
campaign_id: seo
agent:
  enabled_toolsets: [file, terminal, web, browser, skills, memory, session_search, camofox]
tools:
  tool_search:
    enabled: "on"
    eager_toolsets: [file, skills, memory]
skills:
  disabled: []
oma_skills: [seo-audit, analytics]
jobs: []
```

- **Tools:** Use the list as a starting point and adapt it to role limits and explicit opt-outs. Request `camofox` in new campaign records and keep it deferred. The installer checks for both saved `CAMOFOX_URL` and `CAMOFOX_API_KEY` in the default profile; it omits Camofox and copies neither value if either is missing. Tool Search does not grant access. Never save credential values in the record.
- **Skills:** This researcher uses `seo-audit` to investigate organic search issues and `analytics` to interpret measurement evidence. Set `oma_skills` to the exact shared skill IDs the role needs, or leave `[]` if none fits. `skills.disabled` is a denylist for available skills; don't add `skills.enabled` or disable skills just because they aren't in `oma_skills`. Preserve existing preloads when updating an agent.
- **Scheduling:** Leave `jobs: []` unless the role owns a genuine recurring obligation. Declare jobs in the owning agent's record; saving a declaration does not start it. Keep secrets and generated fields such as `effective`, `all-keys`, and `available-keys` out of the authored example.

## `SOUL.md`

Replace the example role and the saves path. Use the actual absolute path under the resolved default Hermes home, not a placeholder or a path inside the future native profile.

```markdown
# SEO Researcher

I identify which search opportunities matter to the campaign's audience and explain the evidence behind each recommendation. I communicate plainly and distinguish confirmed findings from hypotheses and data gaps.

For each assignment I hand back the affected queries or pages, the evidence and its time window, and the next decision it supports. I recommend changes; I do not publish or edit live pages. I raise missing access or uncertain conclusions to the orchestrator.

I save useful decisions, evidence, and blockers as concise Markdown (`.md`) notes in `/absolute/default-hermes-home/oma/agents/seo__researcher/saves/`. When resuming work, I read the relevant notes first. I do not save credentials, transcripts, or deliverables there.
```

## Adapt by role

| Role | What to change |
|---|---|
| Campaign orchestrator | Use `<campaign_id>__orchestrator` and include `kanban` in `agent.enabled_toolsets`. Own planning and task assignment on the campaign board. Use `kanban.auto_decompose: false`. Declare a bounded recurring review as described in `oma-campaigns`; keep specialist handoffs dynamic. |
| Campaign specialist | Use `<campaign_id>__<role>` and the matching `campaign_id`. Give it one evidence, drafting, or review responsibility and a clear handoff. Add `kanban` if it needs to update or close its own assigned tasks. |
| Campaign publisher | Use `<campaign_id>__publisher`. Grant only the tools and destination access needed to apply authorized revisions. Follow the campaign's publishing policy, verify the live result, and record its URL or revision. Publishing alone does not require a scheduled job. |
| Standalone agent | Use an unprefixed stable ID and `campaign_id: null`. Rewrite the persona for its standalone responsibility and do not assume campaign model inheritance, board routing, or publication authority. |

Before handing off, check that `id` matches the directory and, for a campaign role, appears in the owning campaign's roster. Check that the persona and config describe the same responsibility and that `saves/` exists. Validate the agent record before provisioning; YAML validation does not verify the persona, integration access, or schedule activation.
