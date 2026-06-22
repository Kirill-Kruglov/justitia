#!/usr/bin/env python3
"""Run the justitia blind-governance study.

    python run.py --smoke   # fast, seeded correctness pass
    python run.py           # full study (~89k seeded runs; deterministic)

Regenerated output is written under model/results_16/ (git-ignored). The
published evidence is checked into results/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "model"))

from atlas import main  # noqa: E402

if __name__ == "__main__":
    main()
