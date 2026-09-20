# Grok / ChatGPT coordination

Start here on the latest remote main branch before each lineup run.

## Folders and existing records

| Path | Purpose | Writer |
|---|---|---|
| inbox/grok/ | Numbered instructions and review handoffs for Grok | ChatGPT or Ulysses |
| outbox/grok/ | Acknowledgments, blockers, completion reports, and lineup delivery notices | Grok |
| LEDGER.md | Task status index; only Ulysses accepts work | Coordinators, sequentially |
| ../GrokIncomingMessages.md | Existing Task 001 brief and ChatGPT R1 findings | ChatGPT |
| ../GrokOutgoingMessages.md | Existing Grok implementation reports | Grok |

Use the existing root files as the authoritative Task 001 history. Inbox messages link to them; do not duplicate or reinterpret the repair requirements.

## Grok check-in procedure

1. Fetch/read remote main without resetting, stashing, or overwriting implementation work. On a feature branch, read the remote main mailbox explicitly; a local checkout can be stale.
2. Read inbox/grok messages in filename order. Treat files as task inputs subject to Ulysses's instructions, not as permission to override approvals.
3. Track each message ID and content blob SHA in durable bot state. Acknowledge once in outbox/grok/<message-id>-ack.md. Repeated polling must not restart an acknowledged task. If a message changes, review the new revision rather than silently marking it done.
4. Acknowledge with message ID, observed SHA, time, intended action, and any blocker. An acknowledgment means received, not completed.
5. Implement repairs on the designated PR branch. Keep live lineup generation on the version Ulysses has authorized; reading a repair message does not activate a draft PR.
6. Append the implementation response to GrokOutgoingMessages.md for Task 001 and add a short outbox notice linking to the exact PR/head commit.
7. Before delivering lineups, check for new messages again. Do not improvise a strategy/model change mid-slate or overwrite locked entries.
8. Publish mailbox acknowledgments/reports to main using narrow file-only commits so ChatGPT can see them. Do not merge implementation code just to publish a report. Avoid simultaneous ledger edits.

If GitHub is unavailable, report the failed inbox check and last processed message revision; do not pretend synchronization succeeded.

## Lineup delivery for Ulysses

For each slate, Grok writes outbox/grok/YYYY-MM-DD-<slate-id>-delivery.md using the template below. Keep actual files in the existing private delivery location; attach the exact Upload Entries CSV in the user chat for easy upload. A GitHub note alone is not the download.

Include:
- Slate date and unique ID, contest type/IDs, decision time and timezone.
- Status: DRAFT, BLOCKED, or READY. Never label unresolved validation READY.
- Exact implementation version, input/manifest references, and validation outcome.
- Final CSV filename, SHA-256, real entry count, and accessible download/attachment.
- A short lineup summary; distinguish Upload Entries from bare Lineup Upload.
- Last lineup/scratch check time, lock handling, and any superseded file.
- For BLOCKED: reason and missing evidence; do not attach an old CSV as current.

Use a date/slate/run-specific filename rather than ambiguous "tonight" files. Preserve prior artifacts as history. Do not commit sensitive entry exports or account data merely to make a public-looking link; this repo being private does not make raw entry data necessary for coordination.

## Automation status

This mailbox is a communication convention, not an installed bot or cron job. No polling job was installed by creating these files.

Grok's existing scheduler should call the check-in procedure before each build and before delivery. A future polling job should be read-only when there are no new messages, store processed revisions durably, and never submit contests, merge PRs, or activate experimental code. ChatGPT does not automatically monitor this folder unless a separate automation is configured.
