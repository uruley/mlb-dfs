#!/usr/bin/env python3
"""Shortcut: export Builder gates with --profile cash.

Equivalent to:
  python3 lab/export_builder_gates.py --profile cash --out lab/builder-gates-cash.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

# Reuse export_builder_gates main with cash defaults
sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_builder_gates as e

if __name__ == "__main__":
    # Prepend cash profile if user didn't pass --profile
    if "--profile" not in sys.argv:
        sys.argv[1:1] = ["--profile", "cash"]
    if "--out" not in sys.argv:
        sys.argv.extend(["--out", str(e.LAB / "builder-gates-cash.csv")])
    raise SystemExit(e.main())
