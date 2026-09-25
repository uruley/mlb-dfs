# Cash Desk

MLB DraftKings classic cash lineup desk. It reads the public MLB Stats API for tonight's board, builds Log5 matchups, anchors each team's run total to the Vegas implied total, runs a 24-state half-inning chain (10,000 sims per game), and solves the lineup most likely to clear your cash line.

```bash
cd desk
npm install
npm run dev
```

## Vegas anchor

DraftKings total + moneylines come from ESPN's public scoreboard (no key). Implied runs split the total by the no-vig moneyline with a Pythagorean exponent of 1.83. Before the main sims, each offense's reach-base events (BB, HBP, 1B, 2B, 3B, HR) are scaled until pilot sims hit that team's implied total (log-log secant, fixed seed, usually within ~0.05 runs). That folds park, weather, bullpen and lineup quality into the sim, and it moves the opposing pitcher's outcomes too. Games without a posted line stay on the pure stats model. Toggle under **Advanced**.

## Cash-rate objective

Default objective is **P(lineup total ≥ cash line)**, measured on the joint sims (teammates and hitter-vs-opposing-arm correlation included). The mean − λ·stdev solver seeds six candidates (λ 0 → 1.5); each is hill-climbed with single swaps scored on cash rate. Set the cash line under **Advanced** from your recent multiplier results. 110 is a placeholder. The old mean − λ·stdev objective is still selectable.

The solve stays inside the cash rules: $50,000, 2 P / C / 1B / 2B / 3B / SS / 3 OF, no hitter facing a rostered arm, no two starters from the same game, at most three hitters from one club, and a batting-order cut (default 1–5).

Salaries are modeled from the floor until you drop a DraftKings salary CSV. **Upload CSV** is the file DraftKings accepts. This app does not sign into DraftKings.

The Python lab at the repo root is unchanged.
