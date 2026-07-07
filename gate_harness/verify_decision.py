"""Standalone decision.json verifier — closes the runner-bypass gap (§1.7).

The runner enforces the checks; this *separate* verifier ensures nothing
downstream (a report, a memo, a future model's analysis) can cite a decision that
did not go through the runner. Separation is the point: if verification lived
inside the code path that could be bypassed, it would not be verification.

A decision.json is INVALID, unconditionally, if:
  - it has no ``_harness_provenance`` block (no matter how good the numbers are);
  - ``written_by`` is not ``gate_harness.runner.run_gate``;
  - its ``harness_version`` != the current hash of ``gate_harness/*.py``;
  - any required ``*_verified`` / ``*_ran`` flag is missing or not True.

Note on ``harness_version``: this hashes the *working-tree* ``gate_harness/*.py``
(top level, tests excluded), not a git checkout of a referenced commit. That is a
deliberate simplification: a decision is only valid against the exact harness code
currently present. If the harness changed since the run, the decision must be
re-run — which is the safe direction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

WRITTEN_BY = "gate_harness.runner.run_gate"
REQUIRED_TRUE_FLAGS = (
    "prereg_lock_verified",
    "leakage_scan_verified",
    "tautology_check_ran",
    "evaluation_oracle_ran",
)


def _gate_harness_dir() -> Path:
    return Path(__file__).resolve().parent


def harness_version() -> str:
    """Deterministic hash of the top-level gate_harness/*.py sources."""
    parts = []
    for path in sorted(_gate_harness_dir().glob("*.py")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        parts.append(f"{path.name}:{digest}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def verify_decision(decision: dict[str, Any] | str | Path) -> tuple[bool, list[str]]:
    """Return (valid, reasons). Fail closed: any doubt -> invalid."""
    if isinstance(decision, (str, Path)):
        try:
            decision = json.loads(Path(decision).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, [f"cannot read/parse decision.json: {exc}"]

    reasons: list[str] = []
    prov = decision.get("_harness_provenance")
    if prov is None:
        return False, [
            "no _harness_provenance block — decision was not produced by the "
            "runner and is INVALID unconditionally, regardless of its numbers"
        ]

    if prov.get("written_by") != WRITTEN_BY:
        reasons.append(f"written_by is {prov.get('written_by')!r}, expected {WRITTEN_BY!r}")

    current = harness_version()
    if prov.get("harness_version") != current:
        reasons.append(
            f"harness_version mismatch: decision {str(prov.get('harness_version'))[:10]} "
            f"!= current {current[:10]} (harness changed since the run)"
        )

    for flag in REQUIRED_TRUE_FLAGS:
        if prov.get(flag) is not True:
            reasons.append(f"provenance flag {flag!r} is {prov.get(flag)!r}, must be True")

    return (not reasons), reasons


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m gate_harness.verify_decision <decision.json> ...", file=sys.stderr)
        return 2
    rc = 0
    for path in argv:
        valid, reasons = verify_decision(path)
        if valid:
            print(f"VALID   {path}")
        else:
            rc = 1
            print(f"INVALID {path}")
            for r in reasons:
                print(f"        - {r}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
