# Grok outbox

Grok writes replies here on main using narrow documentation-only commits.

## Acknowledgment format

Filename: <message-id>-ack.md

- Message ID and exact inbox content SHA:
- Received at (ISO timestamp):
- Status: received / working / blocked / completed:
- Active implementation branch/version:
- Action or blocker:
- Related PR and exact head commit:
- Next handoff:

Do not overwrite another agent's message. Append dated updates to your own acknowledgment. Complete Task 001 implementation reports still belong in ../../../GrokOutgoingMessages.md; link to the new heading here.

## Lineup delivery format

Filename: YYYY-MM-DD-<slate-id>-delivery.md

- Slate/date/contest:
- Status: DRAFT / BLOCKED / READY:
- Code version:
- Final verification time/timezone:
- Input manifest and validation:
- CSV filename and SHA-256:
- Numeric entry count:
- Upload type: Upload Entries / Lineup Upload:
- Attachment or accessible download:
- Lock handling:
- Supersedes:
- Blockers or limitations:

Attach the final CSV in the user's normal delivery chat. Never mark a draft ready, reuse a stale attachment, or include private account details in a status note.
