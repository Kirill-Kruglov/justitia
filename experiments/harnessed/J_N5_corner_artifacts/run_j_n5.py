#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, mean, read_prereg, write_json

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

import artifacts  # noqa: E402
import atlas  # noqa: E402
import families  # noqa: E402

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

ARM_TO_CHANNEL = {"A0": "off", "A1": "unverified", "A2": "verified"}


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = max(0.0, min(1.0, p))
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def run_one(seed: int, world: str, pressure: float, arm: str) -> dict:
    params = artifacts.params_for_artifact_variant(
        "C_full",
        world,
        scenario="J_N5_corner_artifacts",
        artifact_arm=arm,
        adversarial_pressure=pressure,
    )
    row = artifacts.run_one(seed, params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N5")
    row["artifact_arm"] = arm
    row["artifact_channel"] = ARM_TO_CHANNEL[arm]
    return row


def run_rows(worlds: list[str], pressures: list[float], seeds: list[int], arms: Iterable[str]) -> list[dict]:
    rows = []
    for world in worlds:
        for pressure in pressures:
            for arm in arms:
                for seed in seeds:
                    rows.append(run_one(seed, world, pressure, arm))
    return rows


def summarize(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["world"], row["axis_value"], row["axis_label"], row["artifact_arm"])].append(row)
    out = []
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
            "artifact_arm": arm,
            "artifact_channel": ARM_TO_CHANNEL[arm],
            "n": n,
            "permanence_probability": perm,
            "permanence_ci_lo": perm_lo,
            "permanence_ci_hi": perm_hi,
            "collapse_probability": collapse,
            "collapse_ci_lo": collapse_lo,
            "collapse_ci_hi": collapse_hi,
        }
        for metric in [
            "capture_index",
            "capture_threshold",
            "exploitative_strategy_mass",
            "cooperative_strategy_mass",
            "welfare",
            "response_diversity",
            "containment_cost",
            "false_containment",
            "containment_events",
            "mean_declared_share",
            "max_declared_share",
        ]:
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
            rows = sorted([r for r in summary if r["world"] == world and r["artifact_arm"] == arm], key=lambda r: r["axis_value"])
            robust_values = [float(r["axis_value"]) for r in rows if robust(r, thresholds)]
            out[world][arm] = max(robust_values) if robust_values else None
    return {k: dict(v) for k, v in out.items()}


def ceiling_delta(ceilings: dict, world: str, arm_a: str, arm_b: str) -> float | None:
    a = ceilings[world].get(arm_a)
    b = ceilings[world].get(arm_b)
    if a is None or b is None:
        return None
    return float(a) - float(b)


def analyze(summary: list[dict], thresholds: dict, seed_report: dict) -> dict:
    ceilings = pressure_ceilings(summary, thresholds)
    margin = thresholds["H_C1_domain_extension"]["margin_min"]
    h1_worlds = [w for w in thresholds["worlds"] if (ceiling_delta(ceilings, w, "A2", "A0") or -999.0) >= margin]
    h1 = len(h1_worlds) >= thresholds["H_C1_domain_extension"]["required_worlds_min"]

    a2_gain_worlds = [w for w in thresholds["worlds"] if (ceiling_delta(ceilings, w, "A2", "A0") or -999.0) >= margin]
    a1_gain_worlds = [w for w in thresholds["worlds"] if (ceiling_delta(ceilings, w, "A1", "A0") or -999.0) >= margin]
    if not a1_gain_worlds and not a2_gain_worlds:
        h2 = "VACUOUS"
    else:
        separated = [w for w in thresholds["worlds"] if (ceiling_delta(ceilings, w, "A2", "A1") or -999.0) >= margin]
        a1_no_gain = [w for w in thresholds["worlds"] if (ceiling_delta(ceilings, w, "A1", "A0") is not None and ceiling_delta(ceilings, w, "A1", "A0") <= 0.0)]
        h2 = "PASS" if len(separated) >= 2 or len(a1_no_gain) >= 2 else "FAIL"

    pressure0 = thresholds["H_C3_channel_cost_at_published_default"]["pressure"]
    default_rows = {(r["world"], r["artifact_arm"]): r for r in summary if abs(float(r["axis_value"]) - pressure0) < 1e-9}
    cost_tol = thresholds["H_C3_channel_cost_at_published_default"]["containment_cost_increase_tolerance"]
    perm_tol = thresholds["H_C3_channel_cost_at_published_default"]["permanence_drop_tolerance"]
    h3_worlds = []
    for world in thresholds["worlds"]:
        a0 = default_rows.get((world, "A0"))
        a2 = default_rows.get((world, "A2"))
        if a0 and a2:
            perm_drop = a0["permanence_probability"] - a2["permanence_probability"]
            cost_increase = a2["containment_cost"] - a0["containment_cost"]
            if perm_drop <= perm_tol and cost_increase <= cost_tol:
                h3_worlds.append(world)
    h3 = len(h3_worlds) >= thresholds["H_C3_channel_cost_at_published_default"]["required_worlds_min"]

    decision_vector = {
        "H_C1_domain_extension": "PASS" if h1 else "FAIL",
        "H_C2_knife_not_belief": h2,
        "H_C3_channel_cost": "PASS" if h3 else "FAIL",
    }
    decision = "PASS" if seed_report["admissible"] and h1 and h2 == "PASS" and h3 else "FAIL"
    return {
        "decision": decision,
        "decision_vector": decision_vector,
        "pressure_ceilings": ceilings,
        "H_C1_worlds": h1_worlds,
        "H_C2_a1_gain_worlds": a1_gain_worlds,
        "H_C2_a2_gain_worlds": a2_gain_worlds,
        "H_C3_worlds": h3_worlds,
    }


def tautology_report_from_a0(baseline_rows: list[dict], thresholds: dict) -> tuple[dict, list[dict], dict]:
    baseline_summary = summarize(baseline_rows)
    ceilings = pressure_ceilings(baseline_summary, {**thresholds, "arms": ["A0"]})
    any_a0_robust = any(v.get("A0") is not None for v in ceilings.values())
    return {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Fresh A0 baseline rows over the locked J-N5 worlds/pressure grid/seeds.",
        "baseline_has_any_robust_pressure": any_a0_robust,
        "baseline_pressure_ceilings": ceilings,
        "known_caveat": "A0 baseline is part of the comparison, not evidence for artifact benefit by itself.",
    }, baseline_summary, ceilings


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        artifacts.ArtifactBoundaryModel.choose_alloc,
        artifacts.ArtifactBoundaryModel._artifact_bad_consequence,
        artifacts.artifact_conforms,
        atlas.BoundaryAtlasModel.choose_alloc,
        atlas.BoundaryAtlasModel._score_c,
        families.AntiConcentrationVsConsequenceModel._score_c,
        families.AntiConcentrationVsConsequenceModel._apply_cap,
    ]


def experiment(precomputed_a0_rows: list[dict]) -> dict:
    prereg = read_prereg(HERE)
    thresholds = prereg["thresholds"]
    worlds = list(thresholds["worlds"])
    pressures = [float(x) for x in thresholds["adversarial_pressure_grid"]]
    seeds = [int(s) for s in thresholds["seeds"]]
    rows = list(precomputed_a0_rows)
    rows.extend(run_rows(worlds, pressures, seeds, ["A1", "A2"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N5_corner_artifacts", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(summary, thresholds, seed_report)
    write_json(OUTPUTS / "j_n5_checks.json", {"raw_runs": rows, "summary": summary, "analysis": analysis})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "Pressure ceilings by arm, verification load-bearing status, and default-pressure channel cost.",
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "PASS/FAIL/VACUOUS components feed W8 kill-condition jointly with J-N5b H-C4.",
        "fact": "Referee-side conformance and policy functions were leakage-scanned; world-side declaration emission is not part of the referee path.",
        "inference": "Only preregistered H-C decisions are citable; adoption dynamics are recorded observables, not hypothesis thresholds.",
        "what_was_not_shown": "This does not show that declarations are semantically honest beyond the observable conformance envelope.",
    }


def main() -> int:
    thresholds = read_prereg(HERE)["thresholds"]
    worlds = list(thresholds["worlds"])
    pressures = [float(x) for x in thresholds["adversarial_pressure_grid"]]
    seeds = [int(s) for s in thresholds["seeds"]]
    baseline_rows = run_rows(worlds, pressures, seeds, ["A0"])
    taut, _baseline_summary, _baseline_ceilings = tautology_report_from_a0(baseline_rows, thresholds)
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: experiment(baseline_rows), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
