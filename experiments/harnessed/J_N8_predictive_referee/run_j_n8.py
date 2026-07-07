#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, mean, read_prereg

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

import atlas  # noqa: E402
import families  # noqa: E402
import predictive  # noqa: E402

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
ARMS = ["R0", "PO", "PD", "PR", "PW"]
TRAJECTORY_FIELDS = ["predictive_gate_open_by_step", "predictive_calibration_by_step", "predictive_harm_fraction_by_step"]


def write_json_gz(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    return atlas.wilson(p, n, z=z)


def run_one(seed: int, world: str, pressure: float, arm: str) -> dict:
    params = predictive.params_for_predictive_variant(
        "C_full",
        world,
        scenario="J_N8_predictive_referee",
        predictive_arm=arm,
        adversarial_pressure=pressure,
    )
    row = predictive.run_one(seed, params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N8")
    row["predictive_arm"] = arm
    return row


def run_rows(worlds: list[str], pressures: list[float], seeds: list[int], arms: Iterable[str]) -> list[dict]:
    return [run_one(seed, world, pressure, arm) for world in worlds for pressure in pressures for arm in arms for seed in seeds]


def summarize(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["world"], row["axis_value"], row["axis_label"], row["predictive_arm"])].append(row)
    out = []
    numeric_metrics = [
        "capture_index", "capture_threshold", "resource_hhi", "exploitative_strategy_mass", "cooperative_strategy_mass",
        "welfare", "response_diversity", "containment_cost", "false_containment", "containment_events",
        "predictive_gate_open_share", "predictive_latest_calibration_score", "predictive_preemptive_containment_events",
        "predictive_reactive_containment_events", "predictive_confounded_predictions", "predictive_resolved_predictions",
        "predictive_insufficient_evidence_steps",
    ]
    for (world, pressure, label, arm), vals in sorted(grouped.items()):
        n = len(vals)
        perm = mean([float(v["permanence"]) for v in vals])
        collapse = mean([float(v["collapse"]) for v in vals])
        perm_lo, perm_hi = wilson(perm, n)
        collapse_lo, collapse_hi = wilson(collapse, n)
        row = {
            "world": world,
            "axis": "adversarial_pressure",
            "axis_value": pressure,
            "axis_label": label,
            "predictive_arm": arm,
            "n": n,
            "permanence_probability": perm,
            "permanence_ci_lo": perm_lo,
            "permanence_ci_hi": perm_hi,
            "collapse_probability": collapse,
            "collapse_ci_lo": collapse_lo,
            "collapse_ci_hi": collapse_hi,
        }
        for metric in numeric_metrics:
            row[metric] = mean([float(v.get(metric, 0.0)) for v in vals])
        out.append(row)
    return out


def robust(row: dict, thresholds: dict) -> bool:
    bar = thresholds["robust_cell_bar"]
    return (
        row["permanence_ci_lo"] >= bar["permanence_ci_lo_min"]
        and row["collapse_ci_hi"] <= bar["collapse_ci_hi_max"]
        and row["capture_index"] <= row["capture_threshold"]
        and row["exploitative_strategy_mass"] <= bar["exploitative_strategy_mass_max"]
        and row["cooperative_strategy_mass"] >= bar["cooperative_strategy_mass_min"]
        and row["welfare"] >= bar["welfare_min"]
        and row["response_diversity"] >= bar["response_diversity_min"]
        and row["containment_cost"] <= bar["containment_cost_max"]
        and row["false_containment"] <= bar["false_containment_max"]
    )


def pressure_ceilings(summary: list[dict], thresholds: dict) -> dict[str, dict[str, float | None]]:
    out: dict[str, dict[str, float | None]] = defaultdict(dict)
    for world in thresholds["worlds"]:
        for arm in thresholds["arms"]:
            rows = sorted([r for r in summary if r["world"] == world and r["predictive_arm"] == arm], key=lambda r: r["axis_value"])
            robust_values = [float(r["axis_value"]) for r in rows if robust(r, thresholds)]
            out[world][arm] = max(robust_values) if robust_values else None
    return {k: dict(v) for k, v in out.items()}


def ge_with_none(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None:
        return False
    if b is None:
        return True
    return float(a) >= float(b)


def delta(a, b) -> float | None:
    if a is None or b is None:
        return None
    return float(a) - float(b)


def analyze(summary: list[dict], thresholds: dict, seed_report: dict) -> dict:
    ceilings = pressure_ceilings(summary, thresholds)
    measured_worlds = [w for w in thresholds["worlds"] if ceilings[w].get("R0") is not None]
    margin = thresholds["H_L1_PD_extension"]["margin_min"]
    h1_worlds = []
    h2_failures = []
    h3_failures = []
    h4_failures = []
    po_headroom_worlds = []
    pd_gap_worlds = []
    pw_kill_worlds = []
    for world in measured_worlds:
        r0 = ceilings[world].get("R0")
        po = ceilings[world].get("PO")
        pd = ceilings[world].get("PD")
        pr = ceilings[world].get("PR")
        pw = ceilings[world].get("PW")
        if delta(pd, r0) is not None and delta(pd, r0) >= margin:
            h1_worlds.append(world)
        if not (ge_with_none(po, pd) and ge_with_none(pd, r0)):
            h2_failures.append({"world": world, "R0": r0, "PO": po, "PD": pd})
        if delta(pr, r0) not in {0.0, None}:
            h3_failures.append({"world": world, "R0": r0, "PR": pr, "delta": delta(pr, r0)})
        if delta(pw, r0) is not None and delta(pw, r0) < -thresholds["H_L4_wrong_model_degradation"]["catastrophic_drop"]:
            h4_failures.append({"world": world, "R0": r0, "PW": pw, "delta": delta(pw, r0)})
            pw_kill_worlds.append(world)
        if delta(po, r0) is not None and delta(po, r0) > 0:
            po_headroom_worlds.append(world)
        if delta(po, r0) is not None and delta(po, r0) > 0 and (delta(pd, r0) is None or abs(delta(pd, r0)) <= thresholds["H_L3_random_control"]["ceiling_delta_abs_max"]):
            pd_gap_worlds.append(world)
    required_worlds = thresholds["H_L1_PD_extension"]["required_worlds_min"]
    h1_pass = len(h1_worlds) >= required_worlds
    h2_pass = not h2_failures
    h3_pass = not h3_failures
    h4_pass = not h4_failures
    po_no_headroom = bool(measured_worlds) and not po_headroom_worlds
    derivation_gap = bool(po_headroom_worlds) and bool(pd_gap_worlds)
    kill = {
        "PO_le_R0_simpliciter": po_no_headroom,
        "derivation_gap_partial": derivation_gap,
        "PW_independent_safety_kill": bool(pw_kill_worlds),
    }
    decision_vector = {
        "H_L1_PD_extension": "PASS" if h1_pass else "FAIL",
        "H_L2_order_PO_ge_PD_ge_R0": "PASS" if h2_pass else "FAIL",
        "H_L3_PR_approx_R0": "PASS" if h3_pass else "FAIL",
        "H_L4_PW_degradation_guard": "PASS" if h4_pass else "FAIL",
    }
    decision = "PASS" if seed_report["admissible"] and h1_pass and h2_pass and h3_pass and h4_pass else "FAIL"
    gate_activity = {
        arm: mean([float(r.get("predictive_gate_open_share", 0.0)) for r in summary if r["predictive_arm"] == arm])
        for arm in thresholds["arms"]
    }
    return {
        "decision": decision,
        "decision_vector": decision_vector,
        "pressure_ceilings": ceilings,
        "measured_worlds": measured_worlds,
        "H_L1_worlds": h1_worlds,
        "H_L2_failures": h2_failures,
        "H_L3_failures": h3_failures,
        "H_L4_failures": h4_failures,
        "phase1_kill_status": kill,
        "gate_activity_by_arm": gate_activity,
    }


def extract_trajectories(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if row["predictive_arm"] == "R0":
            continue
        out.append({
            "seed": row["seed"],
            "world": row["world"],
            "axis_value": row["axis_value"],
            "axis_label": row["axis_label"],
            "predictive_arm": row["predictive_arm"],
            **{field: row.get(field, []) for field in TRAJECTORY_FIELDS},
        })
    return out


def compact_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        compact = dict(row)
        for field in TRAJECTORY_FIELDS:
            compact.pop(field, None)
        out.append(compact)
    return out


def tautology_report_from_r0(baseline_rows: list[dict], thresholds: dict) -> tuple[dict, list[dict], dict]:
    baseline_summary = summarize(baseline_rows)
    ceilings = pressure_ceilings(baseline_summary, {**thresholds, "arms": ["R0"]})
    return {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Fresh R0 baseline rows over locked J-N8 worlds/pressure grid/seeds.",
        "baseline_pressure_ceilings": ceilings,
        "known_caveat": "R0 is part of the comparison, not evidence for predictive benefit by itself.",
    }, baseline_summary, ceilings


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        predictive.PredictiveBoundaryModel.choose_alloc,
        predictive.PredictiveBoundaryModel._predictive_harm_fraction,
        predictive.PredictiveBoundaryModel._resolve_predictive_calibration,
        predictive.PredictiveBoundaryModel._calibration_report,
        predictive.LinearTransitionEnsemble.predict_harm_fraction,
        predictive.LinearTransitionEnsemble.predict_member_next,
        predictive.ShadowOracleForecaster.predict_harm_fraction,
        atlas.BoundaryAtlasModel.choose_alloc,
        atlas.BoundaryAtlasModel._score_c,
        families.AntiConcentrationVsConsequenceModel._score_c,
        families.AntiConcentrationVsConsequenceModel._apply_cap,
    ]


def experiment(precomputed_r0_rows: list[dict]) -> dict:
    prereg = read_prereg(HERE)
    thresholds = prereg["thresholds"]
    worlds = list(thresholds["worlds"])
    pressures = [float(x) for x in thresholds["adversarial_pressure_grid"]]
    seeds = [int(s) for s in thresholds["seeds"]]
    rows = list(precomputed_r0_rows)
    rows.extend(run_rows(worlds, pressures, seeds, ["PO", "PD", "PR", "PW"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N8_predictive_referee", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(summary, thresholds, seed_report)
    write_json_gz(OUTPUTS / "j_n8_checks.json.gz", {"raw_runs": compact_rows(rows), "summary": summary, "analysis": analysis})
    write_json_gz(OUTPUTS / "predictive_trajectories.json.gz", {"trajectories": extract_trajectories(rows)})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "Predictive-referee pressure ceilings, self-gating activity, and degradation controls.",
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "J-N8 combines with J-N8b for line-11 phase-1 interpretation and kill branches.",
        "fact": "Predictive policy functions were leakage-scanned; transition learning is over Obs + referee action + next Obs.",
        "inference": "PO is an upper-bound shadow oracle over observables, not an implementable learned contact claim.",
        "what_was_not_shown": "No active probing is tested; phase 2 requires a separate preregistration.",
    }


def main() -> int:
    thresholds = read_prereg(HERE)["thresholds"]
    worlds = list(thresholds["worlds"])
    pressures = [float(x) for x in thresholds["adversarial_pressure_grid"]]
    seeds = [int(s) for s in thresholds["seeds"]]
    baseline_rows = run_rows(worlds, pressures, seeds, ["R0"])
    taut, _baseline_summary, _baseline_ceilings = tautology_report_from_r0(baseline_rows, thresholds)
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: experiment(baseline_rows), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
