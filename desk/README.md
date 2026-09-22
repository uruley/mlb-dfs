# Cash Desk

MLB DraftKings classic cash lineup desk. It reads the public MLB Stats API for tonight's board, builds Log5 matchups, runs a 24-state half-inning chain (10,000 sims per game), and solves one floor-weighted lineup.

```bash
cd desk
npm install
npm run dev
```

The solve stays inside the cash rules: $50,000, 2 P / C / 1B / 2B / 3B / SS / 3 OF, no hitter facing a rostered arm, no two starters from the same game, at most three hitters from one club, and a batting-order cut (default 1–5).

Salaries are modeled from the floor until you drop a DraftKings salary CSV. **Upload CSV** is the file DraftKings accepts. This app does not sign into DraftKings.

The Python lab at the repo root is unchanged.
