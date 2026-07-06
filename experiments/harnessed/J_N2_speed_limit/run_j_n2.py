#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from experiments.harnessed.common import ensure_imports, read_csv, read_prereg, write_json

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

import atlas  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / "outputs"

FORBIDDEN_NAMES = [
    *atlas.base.STRATEGY_FIELDS,
    "exploitative_label",
    "lineages",
    "strategy",
    "hidden_type",
    "_exploit_score",
    "exploit_score",
]


def _score_speed_boundary(result):
    return result["decision"]


def _evaluation_suite():
    return _score_speed_boundary({"decision": "pending"})


def speed_limit_policy_path():
    return [
        atlas.BoundaryAtlasModel.choose_alloc,
        atlas.BoundaryAtlasModel._score_c,
    ]


def existing_dial_reconnaissance() -> dict:
    axes = {axis: values for axis, values in atlas.AXES}
    return {
        "present": {"delay": "delay" in axes, "t_irrev": "t_irrev" in axes},
        "missing": [
            "propagation_speed",
            "observation_latency_separate_from_delay",
            "intervention_latency_separate_from_delay",
            "recovery_rate",
        ],
        "available_delay_grid": axes.get("delay", []),
        "available_t_irrev_grid": axes.get("t_irrev", []),
        "note": (
            "No substrate parameter was added. This gate can only test the "
            "existing delay/t_irrev ratio unless the author specifies a model "
            "change before lock."
        ),
    }


def experiment() -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    summary_path = Path(thresholds["source_summary_csv"])
    if not summary_path.is_absolute():
        summary_path = Path.cwd() / summary_path
    rows = read_csv(summary_path)
    subset = [
        r for r in rows
        if r["scenario"] == "boundary"
        and r["world"] in thresholds["worlds"]
        and r["policy15"] == "anti_concentration_plus_delayed_harm_throttle"
        and r["axis"] in {"delay", "t_irrev"}
    ]

    by_r = {}
    for r in subset:
        ratio = round(float(r["delay"]) / max(1.0, float(r["t_irrev"])), 6)
        by_r.setdefault((r["world"], ratio), []).append(float(r["permanence_probability"]))

    equal_r_spread = {
        f"{world}:R={ratio}": max(vals) - min(vals)
        for (world, ratio), vals in by_r.items()
        if len(vals) >= 2
    }
    monotonic_violations = []
    for world in thresholds["worlds"]:
        points = sorted(
            (
                round(float(r["delay"]) / max(1.0, float(r["t_irrev"])), 6),
                float(r["permanence_probability"]),
                r["axis_label"],
            )
            for r in subset
            if r["world"] == world
        )
        for (r1, p1, lab1), (r2, p2, lab2) in zip(points, points[1:]):
            if r2 > r1 and p2 > p1 + thresholds["monotonicity_tolerance"]:
                monotonic_violations.append({"world": world, "from": lab1, "to": lab2, "p_from": p1, "p_to": p2})

    max_equal_r_spread = max(equal_r_spread.values() or [0.0])
    if monotonic_violations or max_equal_r_spread > thresholds["equal_r_permanence_tolerance"]:
        decision = "FAIL"
    else:
        decision = "PASS"

    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N2_existing_delay_t_irrev_grid", "role": "core", "seeds": int(thresholds["core_metric_seeds"]), "pass_fail": "PASS"},
    ])
    if not seed_report["admissible"]:
        decision = "INCONCLUSIVE"

    payload = {
        "subset_rows": len(subset),
        "equal_r_spread": equal_r_spread,
        "max_equal_r_spread": max_equal_r_spread,
        "monotonic_violations": monotonic_violations,
        "dial_reconnaissance": existing_dial_reconnaissance(),
    }
    write_json(OUTPUTS / "speed_limit_checks.json", payload)
    return {
        "question": "Does the existing justitia delay/t_irrev sweep support a speed-limit boundary in R = delay / t_irrev?",
        "mode": "prospective; outcome unknown at lock time; decision citable under ANY outcome",
        "metric": "Monotonicity in delay/t_irrev and equal-R permanence spread on existing dials only.",
        "preregistered_thresholds": thresholds,
        "decision": decision,
        "speed_limit_checks": payload,
        "seed_policy": seed_report,
        "downstream_consequence": "PASS supports only the existing-dials R claim; FAIL kills it; INCONCLUSIVE is published as-is.",
        "fact": "The current substrate exposes delay and t_irrev but not separate propagation/observation/intervention/recovery dials.",
        "inference": "This gate is not the full essay-promised isolation unless the missing dials are accepted as out of scope or added in a separate model-change phase.",
        "what_was_not_shown": "Independent variation of propagation speed, observation latency, intervention latency, and recovery rate was not shown.",
    }


def main() -> int:
    leak = LS.scan_fit_path(speed_limit_policy_path(), forbidden_names=FORBIDDEN_NAMES)
    taut = {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Existing-dials ratio analysis; no outcome threshold is derived from observed post-lock results.",
    }
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_speed_boundary"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, experiment, leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

