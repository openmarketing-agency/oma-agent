# OMA Agent fork changes and configuration reference

This guide covers **OMA Agent v0.1.6**, compared with the upstream Hermes Agent commit it last incorporated (`fe8b920cae09`). It covers the fork’s behavior and settings, not every inherited Hermes option or every change on newer upstream `main`.[7][11]

**In short:** OMA starts with seven selected toolsets and a smaller skill catalog, exposes four of those toolsets directly and defers the other three, opens the compact `mono` TUI for interactive chat, provides an R2-backed playbook installer, and does not collect or send Nous Shared Metrics. An upgrade does **not** replace an existing profile’s saved tool list or recreate an installed team.[1][2][8]

## 1. What a profile starts with

| Profile | Configuration and identity | Skills and credentials |
| --- | --- | --- |
| Fresh built-in `default` | Minimal OMA starter `config.yaml`. The stock `SOUL.md` identifies it as OMA Agent, built by Open Marketing Agency and powered by Hermes Agent, and points it to `oma-playbooks`. It is the team setup agent, not the orchestrator of any team. | Bundled skills are available on demand where supported; none preloaded. The fresh `.env` starts empty; Docker may write a real gateway key. |
| New named profile, no clone | Same minimal starter policy. Stock `SOUL.md` identifies it as OMA Agent without the root’s playbook-management instruction. | Bundled skills are seeded unless opted out. No skill preload or example `.env` entries. Normal creation can mirror real launch credentials and model settings; an empty seed is not a guarantee of credential isolation. |
| Explicit clone | Uses the source configuration and persona rather than the OMA starter policy. Copy scope and isolation rules still depend on the clone flags. Unset global defaults are still resolved by the installed runtime. | Keeps the clone’s copied skills and `.env` where the clone mode supplies them. A clone does not register a second copy of the source profile’s cron jobs. |
| New playbook agent | Created under its canonical `<playbook-id>__<role-id>` name. The installed `config.yaml` and `SOUL.md` come from the authored role, not from `default` or the generic starter. | Seeds bundled skills and copies the role’s declared `oma_skills`. Blocks the `oma-playbooks` management skill in those roles. Does not mirror launch credentials or register jobs. Hermes’ ordinary shared-auth rules can still apply. |
| Existing profile after upgrade | Saved toolsets, skills settings, display choices, and customized `SOUL.md` are not replaced by the starter. A changed **runtime default** can affect omitted keys; a saved override still wins, except old Shared Metrics opt-ins are inert. | Existing `.env` files are not reinitialized from an example. Missing dotenv files can be seeded empty by profile maintenance. Existing skill packages are not an inventory of what the new release seeds on a clean home. |

The starter is written only for a missing file-backed config. It is shared by source and Docker setup, normal non-clone profile creation, and local config creation through `hermes config edit` or the appropriate doctor repair. Remote config setup does not seed a local shadow config. The annotated [`cli-config.yaml.example`](cli-config.yaml.example) is a reference, not the live file the installer copies.[3][6][8]

### Fresh starter YAML

This is the policy portion of a freshly seeded file. The actual file also has an internal `_config_version` stamp and may have model/provider settings when supplied by setup or profile creation. It does not pin every merged runtime default.[3][8]

```yaml
agent:
  enabled_toolsets: [file, terminal, browser, web, skills, memory, session_search]
tools:
  tool_search:
    enabled: "on"
    eager_toolsets: [file, terminal, skills, memory]
    listing: "off"
skills:
  disabled: []
approvals:
  mode: "off"
  timeout: 300
  cron_mode: approve
  single_query_mode: approve
  unattended_mode: approve
  approvers: ["*"]
  mcp_reload_confirm: false
  destructive_slash_confirm: false
```

**Which file am I looking at?** Run `hermes -p default config path` or `hermes -p <profile> config path` to find the active file. `hermes -p <profile> config get <key>` can show a merged value even when the key is absent from the saved YAML. Use the path command rather than assuming the host’s personal Hermes home is the same as the Docker home. See the [profile commands](website/docs/reference/profile-commands.md) and [starter implementation](hermes_cli/config_home.py).

## 2. Toolsets: what the agent may use

`agent.enabled_toolsets` is a **fork-added profile-wide allowlist**. Its runtime default is `null`, but the fresh OMA starter explicitly writes the seven toolsets shown above. It governs availability, not whether a schema is sent upfront.[1][8]

| `agent.enabled_toolsets` | Effective selection |
| --- | --- |
| Omitted or `null` | Use Hermes’ existing per-platform selection (`platform_toolsets.<platform>`) or platform defaults. |
| A YAML list of toolset names | Replace the per-platform selection for this profile across CLI, TUI, Desktop, messaging, and scheduled runs. Platform eligibility and narrower caller/session restrictions still apply. |
| `[]` | Select no toolsets, including automatic MCP and plugin additions. This does not disable every non-toolset feature or constitute a process sandbox. |
| Malformed list or non-list | Warn and select no toolsets rather than broadening to platform defaults. |

Names are literal and case-sensitive. Bundles expand to their member tools. The inherited `agent.disabled_toolsets` is applied as a final exclusion, including shared tools: disabling `search`, for example, can remove `web_search` while leaving `web_extract` from `web`. With an explicit profile allowlist, `hermes tools` per-platform edits do not override it. To include an MCP server, select its configured name or `mcp-<name>` and keep the server enabled; plugin tools likewise require a working, enabled plugin. Unlisted automatic toolset additions cannot widen the profile’s selection.[1]

| Starter toolset | What it selects |
| --- | --- |
| `file` | File reading, writing, patching, and searching. |
| `terminal` | Terminal commands and process management. |
| `browser` | Browser tools; usable capabilities still depend on the browser backend and other tool requirements. |
| `web` | Web search and extraction; a working provider/backend can still be required. |
| `skills` | The callable `skills_list`, `skill_view`, and `skill_manage` tools. It does not install or preload skills. |
| `memory` | The callable `memory` tool and eligible memory-provider tools. This is separate from the inherited settings `memory.memory_enabled` and `memory.user_profile_enabled`, which control the built-in stores; enabling storage does not select the toolset. |
| `session_search` | Search and recall past conversations. Enabled in fresh profiles starting with v0.1.6, but not eager. |

See [profile toolset resolution](hermes_cli/toolset_policy.py), [toolset definitions](toolsets.py), and the [configuration reference](website/docs/user-guide/configuration.md#global-toolset-allowlist).

## 3. Tool Search: when schemas are visible

Once tools are selected, Tool Search can keep their full schemas out of the initial model request. **Eager** means the model gets a schema directly. **Deferred** means the model can find the tool with `tool_search`, inspect it with `tool_describe`, and invoke it with `tool_call`. The starter has exposed `file`, `terminal`, `skills`, and `memory` directly since v0.1.5. In v0.1.6, `browser`, `web`, and `session_search` are deferred. The bridge stays visible with its upfront catalog hidden. Making the `skills` tools eager does not preload any skills.[1][3]

All keys in this table live under `tools.tool_search`.

| Key | Runtime default | Fresh starter | Behavior |
| --- | --- | --- | --- |
| `eager_toolsets` **(fork-added)** | `null` | `[file, terminal, skills, memory]` | A list keeps members of those selected toolsets eager and defers other selected tools. `[]` defers all selected task tools; the search bridge remains direct when active. Omitted, `null`, or a blank YAML value retains the legacy deferral policy, including `defer_toolsets`. An explicit list takes precedence over both deferral settings. |
| `defer_toolsets` **(fork-added)** | `[]` | Not written | Adds whole toolsets to legacy deferrals, including new members they gain. `[]` or `null` adds none. Ignored when an explicit `eager_toolsets` list is set. |
| `defer` (inherited) | Curated list | Not written | Legacy list of individual tool names. An explicit list replaces the curated one. `[]` clears the built-in per-tool list, not inherent deferral of MCP/non-core plugin tools under legacy policy. |
| `enabled` (inherited) | `"auto"` | `"on"` | `"auto"` and `"on"` activate the bridge when there is anything to defer. `"off"` bypasses the disclosure policy and makes selected local tool schemas direct; it does not disable tools. |
| `listing` (inherited) | `"auto"` | `"off"` | Controls the upfront deferred-tool catalog in the bridge description. `"off"` leaves the bridge and on-demand discovery intact. `"auto"`/`"on"` permit a budgeted listing. |
| `threshold_pct` / `listing_max_tokens` (inherited) | `5` / `4000` | Not written | Listing budget is limited by both a percentage of the model context window and an absolute approximate token cap. These are not tool authorization limits. |
| `search_default_limit` / `max_search_limit` (inherited) | `5` / `25` | Not written | Default result count and configurable upper bound for each tool-search query. |

For example, this **override** keeps just the already selected `file` and `terminal` toolsets direct while retaining on-demand access to the rest, including `skills` and `memory`. `terminal` covers `process_manage` as well as `terminal`; these lists take toolset names, not per-tool names or glob patterns. Composite and shared membership count. Invalid non-list values or non-string entries are warned about and ignored; there is **no** `tools.tool_search.eager` per-tool option. Hosted connector schemas retain their gateway-managed on-demand behavior.[1]

```yaml
tools:
  tool_search:
    enabled: "on"
    eager_toolsets: [file, terminal]
    listing: "off"
```

To use legacy deferrals plus deferred `web` and `browser`, set `eager_toolsets: null` and `defer_toolsets: [web, browser]`; just adding `defer_toolsets` to an unmodified starter will not take effect because its explicit eager list wins. Start a new conversation after changing selection or disclosure; an existing chat can retain pinned tools and prompts. See the [Tool Search guide](website/docs/user-guide/features/tool-search.md#configuration) and [classifier](tools/tool_search.py).

## 4. Skills: installed, allowed, and loaded are different

OMA ships **three bundled packages**: `hermes-agent`, `computer-use`, and `oma-playbooks`. The `computer-use` package has its own platform constraints and does not itself select the `computer_use` model toolset. Forty-two formerly bundled packages moved to the [optional catalog](website/docs/reference/optional-skills-catalog.md), retaining their support assets, including `p5js` export files. Existing installs can have more than three packages. For example, install an optional skill explicitly with `hermes -p <profile> skills install official/creative/humanizer`.[4]

| Setting | Kind and default | Meaning |
| --- | --- | --- |
| `skills.enabled` | **Fork-added**; `null` | Profile-wide skill allowlist. Omitted or `null` adds no restriction. A list accepts exact names (or exact advertised qualified load names); `[]` leaves only essential skills. |
| `skills.platform_enabled` | **Fork-added**; `{}` | Mapping of platform IDs to allowlists. A platform entry intersects with the profile allowlist; it cannot widen it. An omitted or `null` entry adds no restriction; an empty list leaves only essentials on that platform. |
| `skills.disabled` | Inherited; fresh starter writes `[]` | Final exclusion for nonessential skills. A name on both lists stays disabled. To re-enable it, remove the deny entry and check that any active allowlists admit it. |
| `skills.auto_load` | Inherited; effective fresh default `[]` | Reads selected, available skill content into the prompt for a fresh session. It does not install a package or bypass any selection restriction. |
| `skills.external_dirs` / `skills.create_dir` | Inherited | Discover packages from additional directories or choose where the agent writes newly created skills. Neither setting expands an allowlist. |
| `oma_skills` | **Fork-added playbook source metadata**, not live profile YAML | Choose which complete OMA skill packages the playbook installer copies for that role. Omitted or `[]` copies no OMA packages. This does not exclude separately installed or bundled skills. |

`hermes-agent` is the essential-skill exception to ordinary allow/deny selection. Invalid allowlist types warn and restrict to essential skills rather than widening access. Selection applies to discovery, explicit loading, preloads and bundles, not just the help listing. Installed but unselected is not available: creating a package does **not** extend a fixed allowlist. To admit future installed and agent-authored skills without editing an allowlist each time, keep `skills.enabled` omitted or `null` and list only specific exclusions in `skills.disabled`. Platform compatibility, plugin enablement and project trust rules still apply.[1][4]

```yaml
skills:
  enabled: [hermes-agent, humanizer, oma-playbooks]
  platform_enabled:
    telegram: [humanizer]
  disabled: []
  auto_load: []
```

In this example Telegram can select `humanizer` plus essential `hermes-agent` if installed and supported. A profile’s other platforms can select the three listed names subject to the usual gates. This does not make playbook management work outside `default`. The stock root SOUL mentions `oma-playbooks`; generic new named profiles lack that instruction, but their empty denylist does not itself hide the package. Playbook-provisioned roles explicitly exclude it. `--no-skills` opts ordinary new profiles out of nonessential bundled seeding; essential seeding can remain.[1][3][4]

See [skill selection](agent/skill_selection.py), [bundled seeding](tools/skills_sync.py), the [bundled catalog](website/docs/reference/skills-catalog.md), and the [skills guide](website/docs/user-guide/features/skills.md).

## 5. Display, approvals, and environment files

### Display: changed runtime defaults, not new options

| Key | Upstream baseline | OMA | Impact |
| --- | --- | --- | --- |
| `display.interface` | `cli` | `tui` | Ordinary interactive `hermes` / `hermes chat` opens the Ink TUI by default. Use `hermes --cli` for the classic terminal interface or `--tui` for the TUI. Non-interactive routing and fallback to the CLI when configuration cannot be read remain in place. |
| `display.compact` | `false` | `true` | Uses the compact display by default, without overriding an explicit `false`. |
| `display.skin` | `default` | `mono` | The fallback for a missing or blank skin is `mono` on both root and named profiles, including gateway/TUI resolution. An explicitly configured different skin is kept. |

See [shared defaults](hermes_cli/config_defaults.py), [skin resolution](hermes_cli/skin_engine.py), and [TUI docs](website/docs/user-guide/tui.md).[2][8]

### Approvals: starter policy versus runtime fallback

Fresh root and non-clone profiles write the following existing approval keys. Existing or cloned profiles keep their own saved policy; this starter does not change the generic runtime fallback for `approvals.*`.[3]

| Starter key and value | Effect |
| --- | --- |
| `approvals.mode: "off"` | Skip interactive prompts for commands governed by the ordinary approval mode. |
| `approvals.cron_mode: approve` | Auto-approve flagged commands subject to the unattended cron approval policy. Does not create a cron job. |
| `approvals.single_query_mode: approve` | Auto-approve commands covered by the `-q` single-query approval policy. |
| `approvals.unattended_mode: approve` | Auto-approve commands covered by the unattended approval policy, such as API or webhook turns without an approval channel. |
| `approvals.approvers: ["*"]` | Any already-admitted chat member can respond when a supported chat prompt does appear; this is not a chat admission rule. |
| `approvals.timeout: 300` | Remaining unanswered approval prompts expire after 300 seconds. |
| `approvals.mcp_reload_confirm: false` | Skip the `/reload-mcp` confirmation. |
| `approvals.destructive_slash_confirm: false` | Skip the dedicated confirmation for destructive slash commands such as `/clear`, `/new`, `/reset`, and `/undo` on surfaces that honor this setting. |

**Separate runtime change:** `security.protected_instruction_files` now defaults to `false` for all profiles, including existing ones where it is omitted. It was `true` in the upstream baseline. Set it to `true` to require the separate approval for tool writes to `SOUL.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, and covered project-local `.hermes` files. `security.protected_instruction_extra_patterns` adds basename patterns while the gate is enabled. This setting does not change other file-write guards, command deny rules, hard blocks, OS permissions, or tool selection. Review the starter’s approval policy before using it for an unattended or shared profile.[3][8]

### `.env` and SOUL preservation

Fresh source installs and non-cloned named profiles seed a private, empty `.env` instead of copying `.env.example`. Only real values are written by paths that have something to set; Docker still persists a generated `API_SERVER_KEY` when needed. Existing files and explicitly cloned values are preserved by the seeding path. Normal launch credential sharing/mirroring is a separate mechanism. Existing customized `SOUL.md` files are preserved; recognized stock legacy templates can be refreshed to the OMA persona. Configuration belongs in `config.yaml`, not `.env`.[3][6]

## 6. Privacy: Nous Shared Metrics is retired

Since v0.1.4, OMA Agent does **not prompt for, collect, or upload Nous Shared Metrics**. The change applies across profiles; it is not just a default opt-out. `hermes setup telemetry` and the normal consent UI were removed. Legacy `telemetry.shared_metrics.enabled`, `send`, and `endpoint` values may still be present in an old YAML file, but they do not reactivate collection or sending. Legacy dashboard/TUI consent APIs report disabled and cannot save an opt-in.[8][9]

This does not erase historical Shared Metrics artifacts or disable unrelated local logs, local usage diagnostics, update receipts, or ordinary requests to a configured model or tool provider. A running older image does not acquire this change from the release being published; upgrade the runtime that the profile actually uses. See the [retired consent implementation](hermes_cli/observability/shared_metrics_consent.py), [runtime gate](hermes_cli/observability/relay_shared_metrics.py), and [regressions](tests/hermes_cli/test_oma_shared_metrics_removed.py).

## 7. Playbooks: definitions and provisioning, not scheduled work

The bundled [`oma-playbooks` skill](skills/autonomous-ai-agents/oma-playbooks/SKILL.md) runs its helper in the `default` profile. A playbook is a versioned definition of a team, not a fixed pipeline. Its root source `config.yaml` declares `id`, `name`, `version`, `description`, `orchestrator`, and its ordered `agents` list. The orchestrator ID is `<playbook-id>__orchestrator` and must be in the roster. Each agent entry is already a full profile ID, with a matching `agents/<agent-id>/config.yaml` and adjacent `SOUL.md`. The agent YAML carries its matching `id`, `version`, `description`, optional `oma_skills` and `jobs`, plus its native Hermes settings. The installer strips source-only metadata before writing live `config.yaml`.[3][5]

| Helper verb | Effect |
| --- | --- |
| `check` | Resolve an R2 snapshot and report cache status without downloading ZIPs. |
| `fetch` | Cache both ZIPs, without creating profiles. Reuse a complete cache entry for that commit. |
| `catalog` | List available playbooks from the selected snapshot; fetch it if missing. |
| `plan <id>` | Validate the roster and show agent versions, skill dependencies, and declared job IDs. Does not install. |
| `install <id>` | Provision a new team using native named profiles, authored configs and SOULs, and declared skill packages. Does not start agent turns. A fully recorded same-version install is a no-op; version changes, partial records, or profile collisions are not overwritten. |
| `list` / `status <id>` | Inspect local installation records and which profiles still exist; no network access. |

`--tag` pins the public content snapshot; `--version` for `plan`/`install` asserts the playbook’s own version. The two versions are independent of each other and of the OMA Agent Docker tag. `catalog`, `plan` and `install` accept `--repo <trusted-local-checkout>` as an explicit alternative to public discovery. The built-in helper does not have an upgrade, uninstall, or cron-activation verb. See its [argument parser](hermes_cli/oma_playbooks/__main__.py) for the exact interface.[3][5]

**Public downloads:** R2 serves `latest.yaml`, `<tag>/release.yaml`, `<tag>/playbooks.zip`, and `<tag>/skills.zip`. No Git client, GitHub API or GitHub credential is required for public discovery or fetching. Only a `404` on the unpinned `latest.yaml` falls back to the known `v0.1.1` content snapshot; malformed metadata and other errors do not. Both archives must pass validation, including matching the advertised commit in their archive metadata, before the manager publishes the complete cache at `$HERMES_HOME/cache/oma-playbooks-r2/<commit>/`. Fetching a newer bundle does not upgrade installed agents or change existing environments.[5]

**What installation leaves on disk:** `$HERMES_HOME/playbooks/<id>/installation.yaml` contains the roster, versions, states, declared job IDs, scratch paths, and public snapshot provenance where applicable. Beneath the installed playbook, each `agents/<agent-id>/` directory gets a child directory named `tmp`; its absolute path appears in the installed SOUL. The source manifest stays in the cache or in the explicitly supplied checkout, not in the installed ledger directory. OMA skill packages resolve by exact `SKILL.md` name from the shared source `skills/` tree or that playbook’s `skills/` tree; ambiguous names and bundled-name collisions are rejected. The installer does not import launch credentials, seed Kanban tasks, or start the team.[3][5]

**Jobs are declarations only.** An agent’s `jobs` list contains mappings with unique `id` values. The built-in installer records those IDs as `declared_jobs`; it neither validates the rest of the schedule as a native cron configuration nor registers, starts, or runs jobs. Actual cron registration, model/integration setup, and mission activation are separate steps. See [source validation](hermes_cli/oma_playbooks/source.py), [installation](hermes_cli/oma_playbooks/install.py), and [R2 resolution](hermes_cli/oma_playbooks/releases.py).

## 8. Fork-added inspection commands

| Command | What it shows |
| --- | --- |
| `hermes -p <profile> request-dump FILE [--platform PLATFORM] [--prompt TEXT] [--model MODEL] [--provider PROVIDER]` | Writes a fresh provider-native request body for that profile and working directory, not a capture of an active session or its history. Default platform is `cli`; the user prompt is empty unless supplied. No inference or model-selected tool execution. Authentication, metadata or MCP discovery can still contact configured services during initialization. An existing destination is refused. Known secrets are redacted and the file is created owner-only where supported; review it before sharing because it may contain private context or memory. |
| `hermes -p <profile> tools breakdown [--platform PLATFORM] [--json]` | Shows active/direct/deferred tools and approximate per-tool schema and upfront token costs. A deferred full schema is an on-demand cost; any catalog listing is counted in the direct bridge payload, not as an upfront full schema for each deferred tool. |
| `hermes -p <profile> skills breakdown [--platform PLATFORM] [--json]` | Shows selected skills, approximate prompt-index entry size and raw `SKILL.md` size if read, plus the complete index total. A file estimate is not what is necessarily sent upfront. |

The breakdowns are fresh previews for the chosen profile/platform, not measurements of the current chat or billed tokens. Their text tables expand the name column for long MCP/plugin identifiers without truncating them; JSON output is unchanged by alignment. The existing Hermes `console` command’s dispatch moved internally, not its interface. See the [CLI reference](website/docs/reference/cli-commands.md), [exporter](hermes_cli/request_dump.py), and [breakdown implementation](hermes_cli/capability_breakdown.py).[1][2]

## 9. Docker, releases, and maintenance

- **OMA runtime image:** `ghcr.io/openmarketing-agency/oma-agent:v0.1.6`. OMA version tags trigger native builds with release version/revision stamps, architecture smoke tests, and a multi-architecture manifest for `linux/amd64` and `linux/arm64`. The release does not recreate any container. Pull the new tag and recreate the service while retaining its existing Hermes data mount to roll it out. The v0.1.4 workflow is an example of the same release path.[9][10]
- **Secure gateway startup on mounts such as Colima:** If a volume cannot enforce the required owner-only (`0600`) control socket, the gateway uses a private runtime directory rather than advertising an unusable socket. It verifies the socket before accepting clients. This is separate from HTTP gateway authentication and from R2.[6]
- **Separate release tracks:** The fork releases the runtime through the [OMA Docker workflow](.github/workflows/oma-docker-release.yml). The `openmarketing.agency` source repository publishes the playbook/skill content to R2. Updating one does not automatically update the other or installed profiles.[5][7]
- **Repository changes:** Catalog indexes, skill pages and navigation reflect the bundled/optional split; regression coverage and prompt fixtures reflect fork behavior. The contributor guidance dropped an old prompt-snapshot approval note (documentation only), and the fork periodically incorporates upstream Hermes changes. This guide does not count upstream imports as independently authored OMA features.[4][7]

## 10. Upgrade checklist for existing profiles

1. Check `hermes --version` in the runtime you actually use. For Docker, pull and recreate from the OMA tag without replacing the data volume.
2. Inspect `agent.enabled_toolsets`, `tools.tool_search`, `skills`, `display.skin`, and `security.protected_instruction_files` on each target profile. Use `config path` to compare saved keys with the merged values from `config get`.
3. If an older profile’s explicit toolset list lacks `skills`, `memory`, or `session_search`, add the missing names as needed rather than replacing role-specific tools with the starter. To match starter disclosure, set `tools.tool_search.eager_toolsets` to `[file, terminal, skills, memory]`, leaving `session_search` deferred. The upgrade does not rewrite a saved `[]` or custom list. Eager settings never enable toolsets on their own.
4. Start a new session to pick up changed tool/skill policy. Use `tools breakdown` and `skills breakdown` to see what the fresh session can access; do not treat the absence of a full schema upfront as the tool being disabled.
5. Treat content updates and cron setup separately. Check the installed playbook’s `status` before doing anything to a team; fetching content or seeing a declared job in the ledger does not activate anything.

## Comparison basis

The baseline is `fe8b920cae0980cef854f478236f525aaf2b93ce`, the merge base with upstream Hermes `main` for the v0.1.4 release. Neither the v0.1.5 eager starter change nor the v0.1.6 `session_search` addition imports a newer upstream baseline. Reproduce the fork comparison with `git diff fe8b920cae0980cef854f478236f525aaf2b93ce v0.1.6`; comparing directly to a newer upstream tip would mix newer upstream changes into the fork inventory.[7][9][11]

## Sources

[1] https://github.com/openmarketing-agency/oma-agent/pull/1 — OMA Agent PR #1
[2] https://github.com/openmarketing-agency/oma-agent/pull/2 — OMA Agent PR #2
[3] https://github.com/openmarketing-agency/oma-agent/pull/3 — OMA Agent PR #3
[4] https://github.com/openmarketing-agency/oma-agent/pull/4 — OMA Agent PR #4
[5] https://github.com/openmarketing-agency/oma-agent/pull/5 — OMA Agent PR #5
[6] https://github.com/openmarketing-agency/oma-agent/pull/6 — OMA Agent PR #6
[7] https://github.com/openmarketing-agency/oma-agent/pull/7 — OMA Agent PR #7
[8] https://github.com/openmarketing-agency/oma-agent/pull/8 — OMA Agent PR #8
[9] https://github.com/openmarketing-agency/oma-agent/releases/tag/v0.1.4 — OMA Agent v0.1.4 release
[10] https://github.com/openmarketing-agency/oma-agent/actions/runs/44477484530 — v0.1.4 Docker build and publication
[11] https://github.com/NousResearch/hermes-agent/commit/fe8b920cae0980cef854f478236f525aaf2b93ce — Pinned upstream Hermes baseline
