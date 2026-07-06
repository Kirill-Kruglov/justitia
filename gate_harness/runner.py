"""Gate runner — the ONLY sanctioned path to a valid decision.json.

Fixes findings #1/#2/#5/#6 at execution time and closes the runner-bypass gap
(§1.7): before any experiment code runs, ``run_gate`` verifies the prereg lock;
it requires a passing leakage scan and a tautology pre-check; it folds in the
evaluation-oracle log; and it writes ``decision.json`` with a ``_harness_provenance``
signature that ``verify_decision`` (a separate module) checks before any result
can be cited. Flags that only the harness may set (``construction_may_be_tautological``,
``classification_success_depends_on_harness_hint``) are copied verbatim here and
an experiment attempting to override them is rejected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import prereg as _prereg
from .verify_decision import WRITTEN_BY, harness_version

DECISION_NAME = "decision.json"

_HINT_WARNING = (
    "classification success on this control depended on harness-provided "
    "ground-truth hint ({hint_name}={hint_value}); this is NOT evidence of "
    "unsupervised recovery."
)


class RunnerError(RuntimeError):
    pass


def _require_flag_absent_or_equal(result: dict[str, Any], key: str, value: Any) -> None:
    if result.get(key) not in (None, value):
        raise RunnerError(
            f"experiment attempted to override harness-only field {key!r}; "
            f"only the harness may set it"
        )


def run_gate(
    gate_dir: Path,
    experiment_fn: Callable[[], dict[str, Any]],
    *,
    leakage_report: dict[str, Any] | None = None,
    tautology_report: dict[str, Any] | None = None,
    evaluation_oracle_log: list[dict[str, Any]] | None = None,
    write_decision: bool = True,
) -> dict[str, Any]:
    """Verify all preconditions, run the experiment, write a signed decision.json.

    Fail closed: a missing/failed prereg lock, a failed leakage scan, or a missing
    tautology report each raise RunnerError before the experiment runs.
    """
    gate_dir = Path(gate_dir)

    # (1) prereg lock (findings #1/#2)
    ok, reason = _prereg.verify_prereg_lock(gate_dir)
    if not ok:
        raise RunnerError(f"refusing to run {gate_dir.name}: {reason}")

    # (2) leakage scan must have passed (findings #3/#4)
    if not leakage_report or not leakage_report.get("passed"):
        raise RunnerError(
            f"refusing to run {gate_dir.name}: fit-path leakage scan did not pass"
        )

    # (3) tautology pre-check must have run (finding #5)
    if not tautology_report or "construction_may_be_tautological" not in tautology_report:
        raise RunnerError(
            f"refusing to run {gate_dir.name}: tautology pre-check did not run"
        )

    # (4) run the experiment
    result = experiment_fn()
    if not isinstance(result, dict):
        raise RunnerError("experiment_fn must return a dict decision payload (fail closed)")

    # (5) fold in harness-only flags (findings #5/#6), forbidding override
    taut_flag = bool(tautology_report.get("construction_may_be_tautological"))
    _require_flag_absent_or_equal(result, "construction_may_be_tautological", taut_flag)
    result["construction_may_be_tautological"] = taut_flag
    result["information_ratio"] = tautology_report.get("information_ratio")

    hints = [
        e for e in (evaluation_oracle_log or [])
        if e.get("harness_provided_ground_truth_hint")
    ]
    hint_flag = bool(hints)
    _require_flag_absent_or_equal(result, "classification_success_depends_on_harness_hint", hint_flag)
    result["classification_success_depends_on_harness_hint"] = hint_flag
    if hints:
        result["affected_metrics"] = sorted({e.get("hint_name") for e in hints if e.get("hint_name")})
        result["harness_hint_warnings"] = [
            _HINT_WARNING.format(hint_name=e.get("hint_name"), hint_value=e.get("hint_value"))
            for e in hints
        ]

    # (6) provenance signature (§1.7)
    result["_harness_provenance"] = {
        "written_by": WRITTEN_BY,
        "harness_version": harness_version(),
        "prereg_lock_verified": True,
        "leakage_scan_verified": True,
        "tautology_check_ran": True,
        "evaluation_oracle_ran": evaluation_oracle_log is not None,
    }

    if write_decision:
        (gate_dir / DECISION_NAME).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return result
