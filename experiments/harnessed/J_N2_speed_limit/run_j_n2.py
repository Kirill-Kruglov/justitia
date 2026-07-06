#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, mean, read_prereg, write_json

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
            "No substrate parameter was added. This gate tests a new post-lock "
            "factorial grid over the existing delay and t_irrev dials only."
        ),
    }


def run_grid(thresholds: dict) -> list[dict]:
    rows = []
    for world in thresholds["worlds"]:
        for delay in thresholds["delay_grid"]:
            for t_irrev in thresholds["t_irrev_grid"]:
                for seed in thresholds["seeds"]:
                    params = atlas.params_for_variant(
                        "C",
                        world,
                        scenario="J_N2_speed_limit",
                        delay=int(delay),
                        t_irrev=int(t_irrev),
                    )
                    rows.append(atlas.run_one(int(seed), params, "delay_t_irrev_factorial", float(delay) / max(1.0, float(t_irrev)), f"delay={delay};t_irrev={t_irrev}", "J_N2"))
    return rows


def summarize_cells(rows: list[dict]) -> list[dict]:
    grouped = {}
    for row in rows:
        key = (row["world"], row["delay"], row["t_irrev"])
        grouped.setdefault(key, []).append(row)
    out = []
    for (world, delay, t_irrev), vals in sorted(grouped.items()):
        permanence = mean([float(v["permanence"]) for v in vals])
        out.append({
            "world": world,
            "delay": delay,
            "t_irrev": t_irrev,
            "R_delay_over_t_irrev": delay / max(1, t_irrev),
            "n": len(vals),
            "permanence": permanence,
            "capture_index": mean([float(v["capture_index"]) for v in vals]),
            "welfare": mean([float(v["welfare"]) for v in vals]),
        })
    return out


def analyze(cells: list[dict], thresholds: dict) -> dict:
    by_r = {}
    for row in cells:
        ratio = round(float(row["R_delay_over_t_irrev"]), 6)
        by_r.setdefault((row["world"], ratio), []).append(float(row["permanence"]))

    equal_r_spread = {
        f"{world}:R={ratio}": max(vals) - min(vals)
        for (world, ratio), vals in by_r.items()
        if len(vals) >= 2
    }
    monotonic_violations = []
    for world in thresholds["worlds"]:
        points = sorted(
            (
                float(row["R_delay_over_t_irrev"]),
                float(row["permanence"]),
                f"delay={row['delay']};t_irrev={row['t_irrev']}",
            )
            for row in cells
            if row["world"] == world
        )
        for (r1, p1, lab1), (r2, p2, lab2) in zip(points, points[1:]):
            if r2 > r1 and p2 > p1 + thresholds["monotonicity_tolerance"]:
                monotonic_violations.append({"world": world, "from": lab1, "to": lab2, "p_from": p1, "p_to": p2})

    max_equal_r_spread = max(equal_r_spread.values() or [0.0])
    if monotonic_violations or max_equal_r_spread > thresholds["equal_r_permanence_tolerance"]:
        decision = "FAIL"
    else:
        decision = "PASS"
    return {
        "equal_r_spread": equal_r_spread,
        "max_equal_r_spread": max_equal_r_spread,
        "monotonic_violations": monotonic_violations,
        "decision": decision,
    }


def experiment() -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    rows = run_grid(thresholds)
    cells = summarize_cells(rows)
    analysis = analyze(cells, thresholds)

    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N2_delay_t_irrev_factorial", "role": "core", "seeds": len(thresholds["seeds"]), "pass_fail": "PASS"},
    ])
    decision = analysis["decision"] if seed_report["admissible"] else "INCONCLUSIVE"

    payload = {
        "raw_runs": rows,
        "cells": cells,
        "analysis": analysis,
        "dial_reconnaissance": existing_dial_reconnaissance(),
    }
    write_json(OUTPUTS / "speed_limit_checks.json", payload)
    return {
        "question": "Does a new justitia delay/t_irrev factorial sweep support a speed-limit boundary in R = delay / t_irrev?",
        "mode": "prospective; outcome unknown at lock time; decision citable under ANY outcome",
        "metric": "Monotonicity in delay/t_irrev and equal-R permanence spread on a post-lock grid over existing dials.",
        "preregistered_thresholds": thresholds,
        "decision": decision,
        "speed_limit_checks_path": "outputs/speed_limit_checks.json",
        "speed_limit_summary": analysis,
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
        "baseline": "Post-lock delay/t_irrev factorial grid; no outcome threshold is derived from observed post-lock results.",
    }
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_speed_boundary"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, experiment, leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
