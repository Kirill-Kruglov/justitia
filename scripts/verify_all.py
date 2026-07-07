#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gate_harness.verify_decision import verify_decision  # noqa: E402


def main() -> int:
    decisions = sorted((ROOT / "experiments" / "harnessed").glob("*/decision.json"))
    if not decisions:
        print("INVALID no decision.json files under experiments/harnessed")
        return 1
    rc = 0
    for path in decisions:
        valid, reasons = verify_decision(path)
        rel = path.relative_to(ROOT)
        if valid:
            print(f"VALID   {rel}")
        else:
            rc = 1
            print(f"INVALID {rel}")
            for reason in reasons:
                print(f"        - {reason}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

