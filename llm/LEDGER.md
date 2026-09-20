# LLM ledger

Status only. Do not treat this file as a chat log.

- Briefs stay in `GrokIncomingMessages.md` (ChatGPT → Grok). Do not edit a brief after kickoff except to mark accepted / blocked.
- Reports stay in `GrokOutgoingMessages.md` (Grok → ChatGPT). Append; do not rewrite history.
- Only the human marks a task `accepted`.
- One writer per message file. This ledger is the index.

## Board

| id | title | owner | status | brief | report | artifact |
| --- | --- | --- | --- | --- | --- | --- |
| 001 | Pitcher workload evidence + reproducible cash builder | grok | implemented / draft PR / awaiting ChatGPT review | [GrokIncomingMessages.md](../GrokIncomingMessages.md) | [GrokOutgoingMessages.md](../GrokOutgoingMessages.md) | [PR #1](https://github.com/uruley/mlb-dfs/pull/1) |

## Task 001

- **Status:** implemented / draft PR #1 / awaiting ChatGPT review
- **Branch:** `task-001-pitcher-workload` (`709d27ac1fb9762c684974049cd93ce245e4ba61`)
- **PR:** https://github.com/uruley/mlb-dfs/pull/1 (draft, open, base `main`)
- **What shipped:** isolated `cash/` pipeline (evidence-keyed workload, deterministic builder, hash + freshness guards, numeric Entry-ID export) plus fixture tests. GPP builders and `slate_gates.py` left alone.
- **Not done:** human / ChatGPT review; no merge; no live cash run. No 9/18–9/19 snapshots in-repo, so historical replay is still unavailable.
- **Next:** ChatGPT reviews PR #1 against the incoming brief. Human accepts or sends a new incoming task. Do not mark accepted from this file.
