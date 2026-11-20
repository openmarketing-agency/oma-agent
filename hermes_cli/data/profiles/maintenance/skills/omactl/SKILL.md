---
name: omactl
description: Install and maintain self-hosted applications managed by omactl (Open Marketing Agency). Use for catalog discovery, app installation, health checks, troubleshooting, restarts, backups, recovery, updates, domains, and service links on an OMA server.
metadata:
  hermes:
    tags: [omactl, self-hosting, applications, maintenance, docker]
---

# Operate applications with omactl

Use the `terminal` tool to operate the installed `omactl` CLI. Prefer its lifecycle, backup, and recovery operations over direct Docker changes, which bypass its state and rollback handling. Installing this skill does not authorize recurring maintenance or unrelated changes.

## Establish the target

- Run on the intended Ubuntu host as the account that owns the OMA instance. A Hermes container or remote terminal backend may target a different machine; establish host and account before making changes. Do not mount the Docker socket or switch hosts without authorization.
- `omactl` and Docker access must already work. If either is missing, report that prerequisite; use the repository bootstrap script only when server provisioning is requested.
- State defaults to `~/.oma`; retain an existing `OMA_HOME` or consistently use `omactl --home /absolute/instance/path ...`. Do not use sudo merely to bypass a state-directory permission error: that can select root's different instance.
- One Docker daemon supports one OMA instance. A different `--home` does not isolate containers, networks, or volumes.
- Start with `omactl doctor --json` and `omactl status --json`. Inspect `omactl version --json` and command-specific `--help` when needed. For an uninitialized instance, status may fail; initialize only within the requested setup scope.

## Change protocol

1. Scope the requested targets and inspect their current state. Use `--json` for automation; read `ok`, `data`, `warnings`, `error`, and `op_id`, along with the process exit code.
2. Before every CLI mutation, run the same command with `--plan --json`. Inspect `data.targets`, `steps`, `destructive`, and `confirmation`; a successful plan does not prove the real operation will succeed. Error envelopes may carry a plan in `error.details`.
3. Apply the planned command within the user's existing authorization. Ordinary installation or maintenance requests authorize the corresponding non-destructive work; avoid repeated permission questions. Stop for human review on exit 8 and before destructive actions, as required by the omactl agent contract. Reuse explicit approval already given for the exact targets and effects.
4. Verify affected running apps with `omactl verify APP --json`, then inspect status. Verification performs functional checks and may create temporary test records; it is more than container liveness. For intentionally stopped or removed apps, verify the intended stopped/removed status instead of starting them.
5. Report the app/version, resulting state, relevant URLs, verification outcome, backup/snapshot IDs when applicable, and operation IDs or warnings. Do not call an operation successful solely because it exited zero: inspect per-target results too.

Commands below use illustrative app IDs and paths. Substitute discovered values. Every mutation example is subject to the plan/apply/verify protocol above, even when only its applied form is shown.

## Install applications

Discover actual catalog entries first:

```bash
omactl catalog list --json
omactl catalog show wordpress --json
```

Read the app's manifest and its catalog README when available for settings, dependency choices, routes, resources, and setup behavior. Do not invent app IDs, bundles, flags, images, or capabilities. If the requested app is absent, explain that it needs a catalog entry/release; do not install app which is not in the catalog.

For example, install WordPress with non-secret settings:

```bash
omactl install wordpress --set WORDPRESS_ADMIN_EMAIL=ops@example.com --set 'WORDPRESS_SITE_TITLE=My Site' --plan --json
omactl install wordpress --set WORDPRESS_ADMIN_EMAIL=ops@example.com --set 'WORDPRESS_SITE_TITLE=My Site' --json
omactl verify wordpress --json
omactl status wordpress --json
```

Use `install --bundle BUNDLE` only for an existing bundle and `--link CAPABILITY=PROVIDER` when selecting a discovered provider. Review all dependency targets in the plan. omactl installation handles app setup; `omactl setup APP` reruns idempotent setup when diagnosis calls for it. Reinstalling an app with retained volumes may require its original backup repository and saved credentials; do not purge volumes to resolve that condition.

On a new instance, initialize with the existing source checkout's local catalog, e.g. `omactl init --catalog /home/ubuntu/src/omactl/catalog`, plus agreed domain/TLS flags. A source build has no production signing keys by default. A local-catalog warning is expected. Re-running `init` neither refreshes an existing catalog nor changes existing ingress settings. Public DNS, firewall rules, and TLS prerequisites need their own configuration; do not infer a public URL from `localhost`.

## Maintain and troubleshoot

Use bounded diagnostics, avoiding a log stream that never returns:

```bash
omactl status APP --json
omactl logs APP --tail 100 --since 30m --json
omactl history --limit 10 --json
omactl overrides APP --json
```

- For a requested start, stop, or restart, target that app using `omactl start APP`, `stop APP`, or `restart APP`. Avoid `--all` unless the user requested instance-wide work. Restarts can interrupt service.
- Use `omactl verify --all --json` for an authorized whole-instance health check. Use `verify APP --repair` only for requested recovery. `verify --all --repair` preserves apps intentionally stopped by an operator; do not manually start them as a workaround.
- Diagnose before changing configuration. For local runtime fixes, edit only `INSTANCE_HOME/apps/APP/compose.override.yml`, preserving existing overrides. Inspect `omactl overrides APP --json`, preview and apply `restart APP`, and verify again. Report the effective override diff so it can move upstream.
- Do not edit managed `compose.yml`, `compose.generated.yml`, or anything inside the instance `catalog/` as a runtime fix. Catalog development is a separate source-repository task.
- `omactl exec APP --service SERVICE -- COMMAND ...` runs inside an app. Inspect its command help and preview it first. Choose read-only diagnostics unless a write is necessary and authorized; execution is not inherently read-only.
- Do not combine `logs --follow` with `--json`. Redact sensitive log contents before reporting them.
- Stop autonomous repair for `needs_human` or exit 7. For exit 6, rollback succeeded: report the failed change and recovery, inspect the cause, and avoid repeating the same change without new evidence.

## Backups and recovery

Updates, removal, and restore require a configured backup repository. Inspect existing backup configuration/status first; do not replace it or generate a new repository password to fix access to an old repository. Use a user-selected location when initializing a repository:

```bash
omactl backup init --repository /absolute/backup/path --plan --json
omactl backup init --repository /absolute/backup/path --json
omactl backup run --app APP --plan --json
omactl backup run --app APP --json
omactl backup list --app APP --json
omactl backup check --plan --json
omactl backup check --json
```

Backups may briefly stop containers. A same-server backup does not protect against loss of the server. App files alone do not back up named Docker volumes. Use `backup init --env-file /secure/path` for repository credentials; never put secret values in shell arguments or reports.

For recovery, inspect available snapshots, their app/config versions, and the data that would be replaced. Prefer an explicit snapshot ID so the preview and application select the same snapshot:

```bash
omactl restore APP --snapshot SNAPSHOT --plan --json
```

After human approval of that recovery, apply with `--confirm APP`, then verify the app. `--with-config` also restores the matching app definition; use only when that is intended. Never restore, purge, prune backups, or force-remove a provider merely to make a health check pass.

## Updates and scheduling

- Discover update availability with `omactl update APP --check --json`. With a configured trusted release service and working backups, preview/apply `omactl update APP` and verify the app. App arguments limit app updates, but the catalog release is replaced as a whole.
- `omactl self-update --check --json` checks the CLI. Updating the CLI is separate from updating apps and requires its install directory to be writable. Bootstrap installs it in `/usr/local/bin`; do not silently escalate privileges or change ownership for self-update.
- Default source builds refuse untrusted network releases. Do not disable signature validation, trust fixture keys, or repeatedly retry release checks. Explain the missing production release configuration. A requested source rebuild updates the binary, not the installed catalog or running apps automatically.
- Install native schedules only when recurring maintenance is requested: inspect `omactl schedule status --json`, then plan/apply `schedule install`. First establish working backups, manual verification, and the intended update policy. For a local-catalog source deployment without a release service, set the existing instance `omactl.yml` field `updates` to `off` before enabling schedules, preserving unrelated configuration. Do not add duplicate Hermes cron jobs for the same maintenance.

## Domains, connections, removal, and secrets

- Inspect `omactl domain list APP --json`; use `domain add APP HOST` or `domain remove APP HOST` for extra routes. These commands do not provision DNS, open firewalls, or necessarily change the app's canonical URL. WordPress needs separate application-level URL configuration when that URL changes.
- Inspect catalog capabilities before `omactl link CONSUMER PROVIDER --capability NAME` or `unlink ...`. Verify affected apps and explain any dependent-service impact.
- Preview `omactl remove APP`; it takes a final backup and retains volumes by default. Purge deletes volumes and needs `--confirm APP`. Removing a provider with consumers requires `--force` and degrades those consumers; review that impact with the human. Traefik cannot be removed via `remove`.
- `credentials` intentionally returns unredacted secrets. Do not run it for routine status or paste its output into conversation, logs, or reports. Direct the operator to retrieve credentials privately when needed. Do not read whole `.env` or `secrets/backup.env` files into model context, or pass secrets through `--set`, `--env`, or `exec` arguments. Prefer generated app credentials, protected environment files, and hook stdin.
- Installing an app does not automatically give Hermes authenticated WordPress access. Content administration requires separately configured credentials/integration; do not confuse application lifecycle management with that access.

## Exit handling

| Exit | Response |
| --- | --- |
| 0 | Inspect envelope and per-target results; verify the outcome. |
| 1 | Inspect execution error, bounded logs, and operation history. |
| 2 | Check installed command help and correct usage. |
| 3 | Resolve the reported prerequisite or policy condition. |
| 4 | Inspect concurrent work; wait or retry once after it completes. Never delete a live lock. |
| 5 | Diagnose failed functional verification; repair only within scope. |
| 6 | Change failed but rollback succeeded; investigate before another change. |
| 7 | Rollback failed; stop and escalate with redacted operation evidence. |
| 8 | Stop and review the returned plan with the master agent; do not auto-fill confirmation. |
| 9 | Recheck catalog/app/snapshot/capability IDs; do not invent replacements. |

Read error `hint` and `details` before retrying. Stop when the same failure repeats without a new diagnosis; preserve operation IDs and provide a concrete next step.
