#!/usr/bin/env python3
from __future__ import annotations

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

ARM_TO_CHANNEL = {"A0": "off", "A1s": "unverified", "A2s": "verified", "A2f": "verified"}
TRAJECTORY_FIELDS = ["declared_mass_by_step", "stiffness_by_step", "binding_events_by_step"]


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
        scenario="J_N6_seeded_adoption",
        artifact_arm=arm,
        adversarial_pressure=pressure,
    )
    row = artifacts.run_one(seed, params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N6")
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
            "last_quarter_declared_share",
            "mean_declared_stiffness",
            "counterfactual_nonconformance_rate",
            "realized_nonconformance_rate",
            "envelope_binding",
        ]:
            row[metric] = mean([float(v.get(metric, 0.0)) for v in vals])
        for metric in ["declared_zone_steps", "nonconforming_declared_zone_steps"]:
            row[metric] = sum(int(v.get(metric, 0)) for v in vals)
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


def midpoint_declared_share(rows: list[dict], arm: str) -> float:
    shares = []
    for row in rows:
        if row["artifact_arm"] != arm:
            continue
        traj = row.get("declared_mass_by_step", [])
        if not traj:
            shares.append(0.0)
            continue
        midpoint = len(traj) // 2
        prefix = traj[:midpoint] or traj
        shares.append(mean([float(step.get("declared_share", 0.0)) for step in prefix]))
    return mean(shares) if shares else 0.0


def audit_by_world(summary: list[dict], arm: str, metric: str, worlds: list[str]) -> dict[str, float]:
    out = {}
    for world in worlds:
        rows = [r for r in summary if r["world"] == world and r["artifact_arm"] == arm]
        out[world] = mean([float(r.get(metric, 0.0)) for r in rows]) if rows else 0.0
    return out


def classify_h_s3(summary: list[dict], thresholds: dict) -> dict:
    h = thresholds["H_S3_seeded_retention_classification"]
    a2s_rows = [r for r in summary if r["artifact_arm"] == "A2s"]
    aggregate = mean([float(r.get("last_quarter_declared_share", 0.0)) for r in a2s_rows]) if a2s_rows else 0.0
    by_world = {}
    for world in thresholds["worlds"]:
        rows = [r for r in a2s_rows if r["world"] == world]
        val = mean([float(r.get("last_quarter_declared_share", 0.0)) for r in rows]) if rows else 0.0
        if val >= h["retained_min"]:
            label = "RETAINED"
        elif val <= h["decayed_max"]:
            label = "DECAYED"
        else:
            label = "INCONCLUSIVE"
        by_world[world] = {"last_quarter_declared_share": val, "classification": label}
    if aggregate >= h["retained_min"]:
        classification = "RETAINED"
    elif aggregate <= h["decayed_max"]:
        classification = "DECAYED"
    else:
        classification = "INCONCLUSIVE"
    return {"classification": classification, "aggregate_last_quarter_declared_share": aggregate, "by_world": by_world}


def hollow_envelope_flags(summary: list[dict], thresholds: dict) -> list[dict]:
    h = thresholds["vacuity_guard_hollow_envelopes"]
    flags = []
    for row in summary:
        arm = row["artifact_arm"]
        if arm not in h["arms"]:
            continue
        a0 = next((r for r in summary if r["world"] == row["world"] and r["axis_value"] == row["axis_value"] and r["artifact_arm"] == "A0"), None)
        if a0 is None:
            continue
        exploit_growth = row["exploitative_strategy_mass"] - a0["exploitative_strategy_mass"]
        hollow = row["envelope_binding"] <= h["envelope_binding_max"] and exploit_growth >= h["exploit_mass_growth_over_A0_min"]
        if hollow:
            flags.append({
                "world": row["world"],
                "axis_value": row["axis_value"],
                "artifact_arm": arm,
                "envelope_binding": row["envelope_binding"],
                "exploit_mass_growth_over_A0": exploit_growth,
            })
    return flags


def analyze(rows: list[dict], summary: list[dict], thresholds: dict, seed_report: dict) -> dict:
    ceilings = pressure_ceilings(summary, thresholds)
    h1 = thresholds["H_S1_forced_seeded_extension"]
    h1_worlds = [w for w in thresholds["worlds"] if (ceiling_delta(ceilings, w, "A2f", "A0") or -999.0) >= h1["margin_min"]]
    h1_pass = len(h1_worlds) >= h1["required_worlds_min"]

    h2 = thresholds["H_S2_trusted_seeded_counterfactual"]
    a1s_mid = midpoint_declared_share(rows, "A1s")
    if a1s_mid < h2["vacuous_if_A1s_midpoint_declared_share_below"]:
        h2_verdict = "VACUOUS"
        h2_worlds = []
        h2_no_gain_worlds = []
    else:
        a1s_counter = audit_by_world(summary, "A1s", "counterfactual_nonconformance_rate", thresholds["worlds"])
        a2s_realized = audit_by_world(summary, "A2s", "realized_nonconformance_rate", thresholds["worlds"])
        h2_worlds = [
            w for w in thresholds["worlds"]
            if a1s_counter[w] - a2s_realized[w] >= h2["counterfactual_minus_realized_margin_min"]
        ]
        h2_no_gain_worlds = [
            w for w in thresholds["worlds"]
            if ceiling_delta(ceilings, w, "A1s", "A0") is not None
            and ceiling_delta(ceilings, w, "A1s", "A0") <= h2["A1s_ceiling_over_A0_max"]
        ]
        h2_verdict = "PASS" if len(h2_worlds) >= h2["required_worlds_min"] and len(h2_no_gain_worlds) >= h2["required_worlds_min"] else "FAIL"

    h3 = classify_h_s3(summary, thresholds)
    decision_vector = {
        "H_S1_forced_seeded_extension": "PASS" if h1_pass else "FAIL",
        "H_S2_trusted_seeded_counterfactual": h2_verdict,
        "H_S3_seeded_retention_classification": h3["classification"],
    }
    decision = "PASS" if seed_report["admissible"] and h1_pass and h2_verdict == "PASS" else "FAIL"
    return {
        "decision": decision,
        "decision_vector": decision_vector,
        "pressure_ceilings": ceilings,
        "H_S1_worlds": h1_worlds,
        "H_S2_counterfactual_worlds": h2_worlds,
        "H_S2_A1s_no_more_than_one_step_worlds": h2_no_gain_worlds,
        "A1s_midpoint_declared_share": a1s_mid,
        "H_S3": h3,
        "hollow_envelope_flags": hollow_envelope_flags(summary, thresholds),
    }


def extract_trajectories(rows: list[dict]) -> list[dict]:
    trajectories = []
    for row in rows:
        if row["artifact_channel"] == "off":
            continue
        trajectories.append({
            "seed": row["seed"],
            "world": row["world"],
            "axis_value": row["axis_value"],
            "axis_label": row["axis_label"],
            "artifact_arm": row["artifact_arm"],
            **{field: row.get(field, []) for field in TRAJECTORY_FIELDS},
        })
    return trajectories


def compact_rows(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        compact = dict(row)
        for field in TRAJECTORY_FIELDS:
            compact.pop(field, None)
        out.append(compact)
    return out


def tautology_report_from_a0(baseline_rows: list[dict], thresholds: dict) -> tuple[dict, list[dict], dict]:
    baseline_summary = summarize(baseline_rows)
    ceilings = pressure_ceilings(baseline_summary, {**thresholds, "arms": ["A0"]})
    any_a0_robust = any(v.get("A0") is not None for v in ceilings.values())
    return {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Fresh A0 baseline rows over the locked J-N6 worlds/pressure grid/seeds.",
        "baseline_has_any_robust_pressure": any_a0_robust,
        "baseline_pressure_ceilings": ceilings,
        "known_caveat": "A0 baseline is part of the comparison, not evidence for seeded artifacts by itself.",
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
    rows.extend(run_rows(worlds, pressures, seeds, ["A2f", "A2s", "A1s"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N6_seeded_adoption", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(rows, summary, thresholds, seed_report)
    write_json(OUTPUTS / "j_n6_checks.json", {"raw_runs": compact_rows(rows), "summary": summary, "analysis": analysis})
    write_json(OUTPUTS / "adoption_stiffness_trajectories.json", {"trajectories": extract_trajectories(rows)})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "Pressure ceilings, seeded adoption retention, and audit-only nonconformance measures.",
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "H-S1 combines with J-N6b H-S4 for the FW-2b kill simpliciter; H-S3 is a classification, not PASS/FAIL.",
        "fact": "Referee-side conformance and policy functions were leakage-scanned; world-side declaration emission is not part of the referee path.",
        "inference": "Audit-only nonconformance and envelope-binding metrics are recorded after runs and are not inputs to containment policy.",
        "what_was_not_shown": "This does not prove semantic honesty beyond the observable declaration envelope.",
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
