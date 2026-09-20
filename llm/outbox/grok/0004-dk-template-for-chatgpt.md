# Outbox 0004 — DK Classic slate template for ChatGPT

- From: Grok / MLB Manager (Ulysses requested)
- To: ChatGPT
- Time: 2026-09-20

## What

Ulysses provided today’s DraftKings **Classic slate template** (salary / player pool CSV). It is in the repo for you.

**Path:** `fixtures/dk-templates/2026-09-20-classic-slate.csv`  
**SHA-256:** 3caa6b3dfcb8d3179bbff7eed62a45ac18f97d9782d8f5d1dff144d44f230a71  
**Shape:** DK Lineup Upload header `P,P,C,1B,2B,3B,SS,OF,OF,OF` + Instructions, then player pool (`Position`, `Name`, `ID`, `Salary`, `Game Info`, …). Games dated **2026-09-20**.

## How to get it

**Browser / raw (private repo — must be logged into GitHub as an account with access):**  
https://github.com/uruley/mlb-dfs/blob/main/fixtures/dk-templates/2026-09-20-classic-slate.csv  

Raw:  
https://github.com/uruley/mlb-dfs/raw/main/fixtures/dk-templates/2026-09-20-classic-slate.csv  

**CLI:**
```bash
gh api repos/uruley/mlb-dfs/contents/fixtures/dk-templates/2026-09-20-classic-slate.csv \
  --jq .content | base64 -d > 2026-09-20-classic-slate.csv

# or with git
git fetch origin main
git show origin/main:fixtures/dk-templates/2026-09-20-classic-slate.csv > 2026-09-20-classic-slate.csv
```

## Notes

- This is the **slate template / player pool**, not an Upload Entries file (no Entry IDs).
- Ephemeral nightly CSVs stay gitignored; fixtures under `fixtures/` are the intentional exception for handoffs like this.
