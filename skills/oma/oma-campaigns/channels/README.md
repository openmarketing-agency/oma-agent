# Channel rules

One file per channel, shared by every campaign that uses it. Follow the rules for every channel used in the campaign's plans. Each agent's SOUL points to the files for the channels it works on, and the publisher's always does.

These rules cover the platform and the law. Craft rules live in each play's `rules.md`; business-specific constraints go in the campaign's `plans` and relevant personas.

The publisher uses the campaign's authorized official connector when it supports the exact action, account, and target and the platform and venue permit it. For new posts and replies, save a publication first: `yolo` auto-approves without asking; `approve` and `control` require human approval of the exact revision. For authorized edits to existing live content, apply only the requested changes and verify them without requesting publication approval. This distinction does not grant provider access or override platform, venue, or budget rules. If access is unavailable, report the blocker or hand off material where permitted. `control` runs no campaign cron, including analytics.

Rules change. Each file says when it was checked; re-check the sources before relying on a file that is more than three months old. To change rules for one business, copy a file to `oma/plays/channels/<channel>.md` under the default Hermes home and edit the copy; it takes precedence over the bundled file.
