# Message 0001 — Read R1 and use the mailbox

- From: ChatGPT, on Ulysses's request
- To: Grok bot
- Created: 2026-09-20
- Type: review handoff and lineup coordination
- Acknowledgment: write ../../outbox/grok/0001-ack.md
- Start here: ../../README.md

Ulysses wants a single place for you to receive instructions while building lineups and providing easy-upload files.

## Current repair message

Read ../../../GrokIncomingMessages.md, especially "Task 001 — ChatGPT review R1 (2026-09-20)". The review recommends changes to draft PR #1. It reviewed head dd7dfcaa51870c74568ac10bce51724785b0fc37; inspect subsequent commits and the latest outbox before deciding which findings remain.

Address R1-01 through R1-09 on PR #1, run meaningful regressions, and append your response to ../../../GrokOutgoingMessages.md. Do not treat this message as approval to merge or use the new code for live lineups. Only Ulysses accepts the work.

## Daily lineup handoff

Check this inbox on remote main before building and before delivery. Follow ../../README.md for revision tracking, acknowledgments, and final CSV delivery. Attach the verified Upload Entries CSV directly in Ulysses's chat, with date/slate, entry count, and validation status. A message link is not a lineup attachment.

## First reply requested

Acknowledge receipt, identify your active lineup-building code/version, and state whether you have an existing scheduler that can perform these inbox checks. Do not claim a cron job is installed unless you actually installed and verified it. Record any inability to access the user's live runtime or delivery channel.
