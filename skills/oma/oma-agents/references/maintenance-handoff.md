# Maintenance handoff for owned-channel hosting

Use the existing standalone `maintenance` profile and its `omactl` skill for authorized infrastructure work. Do not create a campaign-specific maintenance profile, add `maintenance` to `agents`, or list `omactl` under a campaign agent's `oma_skills`. A working `omactl` CLI and access to the intended OMA host are separate prerequisites.

## Route the request

1. The campaign orchestrator records the infrastructure dependency on its own board. Include the campaign board and task ID, target workspace and domain, intended app or requirement, what must be preserved, and the outcome to verify. If the website, blog, and docs can share one CMS, reuse a single hosting request.
2. `default` verifies the `maintenance` profile and queues one task assigned to `maintenance` on the explicitly designated operations board, or explicitly on `default` if there is no operations board. Cross-reference the campaign and operations task IDs. A campaign profile is pinned to its own board: it must not bypass that boundary or try to assign cross-board work itself. If `default` cannot broker the request, report it for the workspace operator rather than assuming an automatic bridge.
3. `maintenance` loads `omactl`. It checks the intended instance, installed apps, and actual catalog before selecting an app. For authorized mutations, follow the skill's `--plan --json` → apply → verify procedure. If the correct app is absent, host or DNS access is missing, or confirmation is required, report the blocker. Onboarding or a queued task alone is not approval for destructive actions, credential changes, or restarts.
4. `maintenance` returns the app ID, host, verified route, checks performed, and remaining prerequisites on the operations task. `default` relays that result to the campaign board. The campaign publisher separately verifies CMS write access and applies authorized content; a healthy host is not a published website, blog, or docs hub.

## Example operations task

- **Title:** Prepare WordPress hosting for the shared website, blog, and docs.
- **Assignee:** `maintenance` on the workspace's operations board.
- **Request:** For the agreed client instance, check whether the existing self-hosted WordPress app can serve the approved domain. If it exists, reuse it and report its route; do not reinstall it. If missing, discover the actual `wordpress` catalog entry and preview installation under the requested scope. Apply only authorized non-destructive work. Report functional verification and any separate CMS access, domain, DNS, or TLS work still needed. Do not publish pages or share credentials.
- **Done when:** The operation result includes its source campaign task, verified app and route, and any blockers. If no hosting change was authorized or needed, return the read-only findings.
