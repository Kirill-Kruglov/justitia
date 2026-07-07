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

ARM_TO_CHANNEL = {"A0": "off", "F1": "verified", "P0": "unverified", "P1-low": "verified", "P1-high": "verified"}
TRAJECTORY_FIELDS = [
    "declared_mass_by_step",
    "stiffness_by_step",
    "binding_events_by_step",
    "stake_balance_by_step",
    "stake_events_by_step",
]


def write_json_gz(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = max(0.0, min(1.0, p))
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mx = mean(xs)
    my = mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(vx * vy)


def run_one(seed: int, world: str, pressure: float, arm: str) -> dict:
    params = artifacts.params_for_artifact_variant(
        "C_full",
        world,
        scenario="J_N7_bonded_envelope",
        artifact_arm=arm,
        adversarial_pressure=pressure,
    )
    row = artifacts.run_one(seed, params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N7")
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
            "resource_hhi",
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
            "mean_declared_resource_concentration",
            "max_declared_resource_concentration",
            "counterfactual_nonconformance_rate",
            "realized_nonconformance_rate",
            "envelope_binding",
            "total_stake_deposited",
            "total_stake_returned",
            "total_stake_burned",
            "total_tax_burned",
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


def best_p1_ceiling(ceilings: dict, world: str) -> float | None:
    vals = [ceilings[world].get("P1-low"), ceilings[world].get("P1-high")]
    vals = [float(v) for v in vals if v is not None]
    return max(vals) if vals else None


def world_average(summary: list[dict], world: str, arm: str, metric: str) -> float:
    rows = [r for r in summary if r["world"] == world and r["artifact_arm"] == arm]
    return mean([float(r.get(metric, 0.0)) for r in rows]) if rows else 0.0


def classify_retention(summary: list[dict], thresholds: dict) -> dict:
    h = thresholds["H_P5_bonded_retention"]
    out = {}
    for arm in h["arms"]:
        rows = [r for r in summary if r["artifact_arm"] == arm]
        val = mean([float(r.get("last_quarter_declared_share", 0.0)) for r in rows]) if rows else 0.0
        if val >= h["retained_min"]:
            label = "RETAINED"
        elif val <= h["decayed_max"]:
            label = "DECAYED"
        else:
            label = "INCONCLUSIVE"
        out[arm] = {"last_quarter_declared_share": val, "classification": label}
    return out


def wealth_retention_correlation(rows: list[dict], arm: str) -> float | None:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        if row["artifact_arm"] != arm:
            continue
        initial = row.get("artifact_initial_zone_mass", [])
        trajectory = row.get("declared_mass_by_step", [])
        if not initial or not trajectory:
            continue
        last = trajectory[int(len(trajectory) * 0.75):] or trajectory
        for zone in range(len(initial)):
            shares = [float(step.get("declared_by_zone", [0] * len(initial))[zone]) for step in last]
            xs.append(float(initial[zone]))
            ys.append(mean(shares))
    return pearson(xs, ys)


def analyze(rows: list[dict], summary: list[dict], thresholds: dict, seed_report: dict) -> dict:
    ceilings = pressure_ceilings(summary, thresholds)
    measured_worlds = [w for w in thresholds["worlds"] if ceilings[w].get("A0") is not None]

    hp1 = thresholds["H_P1_bonded_separation"]
    hp1_worlds = []
    for world in measured_worlds:
        f1 = world_average(summary, world, "F1", "realized_nonconformance_rate")
        p1h = world_average(summary, world, "P1-high", "realized_nonconformance_rate")
        if f1 - p1h >= hp1["F1_minus_P1_high_margin_min"]:
            hp1_worlds.append(world)
    hp1_pass = len(hp1_worlds) >= hp1["required_worlds_min"]

    hp2 = thresholds["H_P2_domain"]
    l1_worlds = []
    l2_worlds = []
    for world in measured_worlds:
        a0 = ceilings[world].get("A0")
        best = best_p1_ceiling(ceilings, world)
        if a0 is None or best is None:
            continue
        if best >= a0:
            l1_worlds.append(world)
        if best >= a0 + hp2["L2_extension_margin_min"]:
            l2_worlds.append(world)
    hp2_l1 = len(l1_worlds) >= max(1, len(measured_worlds)) if measured_worlds else False
    hp2_l2 = len(l2_worlds) >= hp2["L2_required_worlds_min"]

    hp4 = thresholds["H_P4_concentration_guard"]
    hp4_failures = []
    for world in measured_worlds:
        a0_capture = world_average(summary, world, "A0", "capture_index")
        a0_conc = world_average(summary, world, "A0", "resource_hhi")
        for arm in ["P1-low", "P1-high"]:
            cap = world_average(summary, world, arm, "capture_index")
            conc = world_average(summary, world, arm, "mean_declared_resource_concentration")
            if cap > a0_capture + hp4["capture_index_tolerance"] or conc > a0_conc + hp4["declared_resource_concentration_tolerance"]:
                hp4_failures.append({"world": world, "arm": arm, "capture_index": cap, "declared_resource_concentration": conc, "A0_capture_index": a0_capture, "A0_resource_hhi": a0_conc})
    hp4_pass = not hp4_failures

    retention = classify_retention(summary, thresholds)
    p0 = {
        "P0_pressure_ceilings": {w: ceilings[w].get("P0") for w in thresholds["worlds"]},
        "P1_best_pressure_ceilings": {w: best_p1_ceiling(ceilings, w) for w in thresholds["worlds"]},
        "reading_if_P0_approx_P1": thresholds["P0_preregistered_readings"]["P0_approx_P1"],
        "reading_if_P0_fails_but_P1_works": thresholds["P0_preregistered_readings"]["P0_fails_but_P1_works"],
    }
    decision_vector = {
        "H_P1_bonded_separation": "PASS" if hp1_pass else "FAIL",
        "H_P2_L1_parity_recovery": "PASS" if hp2_l1 else "FAIL",
        "H_P2_L2_extension": "PASS" if hp2_l2 else "FAIL",
        "H_P4_concentration_guard": "PASS" if hp4_pass else "FAIL",
        "H_P5_bonded_retention": retention,
    }
    decision = "PASS" if seed_report["admissible"] and hp1_pass and hp2_l1 and hp4_pass else "FAIL"
    return {
        "decision": decision,
        "decision_vector": decision_vector,
        "pressure_ceilings": ceilings,
        "measured_worlds": measured_worlds,
        "H_P1_worlds": hp1_worlds,
        "H_P2_L1_worlds": l1_worlds,
        "H_P2_L2_worlds": l2_worlds,
        "H_P4_failures": hp4_failures,
        "wealth_retention_correlation": {arm: wealth_retention_correlation(rows, arm) for arm in ["P0", "P1-low", "P1-high"]},
        "P0_pattern": p0,
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
    return {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Fresh A0 baseline rows over the locked J-N7 worlds/pressure grid/seeds.",
        "baseline_pressure_ceilings": ceilings,
        "known_caveat": "A0 baseline is part of the comparison, not evidence for bonded artifacts by itself.",
    }, baseline_summary, ceilings


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        artifacts.ArtifactBoundaryModel.choose_alloc,
        artifacts.ArtifactBoundaryModel._artifact_bad_consequence,
        artifacts.ArtifactBoundaryModel._settle_artifact_stakes,
        artifacts.ArtifactBoundaryModel._apply_zone_dynamics,
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
    rows.extend(run_rows(worlds, pressures, seeds, ["F1", "P0", "P1-low", "P1-high"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N7_bonded_envelope", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(rows, summary, thresholds, seed_report)
    write_json(OUTPUTS / "j_n7_checks.json", {"raw_runs": compact_rows(rows), "summary": summary, "analysis": analysis})
    write_json_gz(OUTPUTS / "bonded_trajectories.json.gz", {"trajectories": extract_trajectories(rows)})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "Bonded envelope pressure ceilings, nonconformance separation, concentration guard, and retention.",
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "H-P2 L1 combines with J-N7b H-P3 directional for the FW-3 kill condition.",
        "fact": "Escrow/referee functions were leakage-scanned; stake-state is public zone-level collateral state, not strategy state.",
        "inference": "Burned stake and P0 tax are deflationary: burned resources leave the world and are not redistributed.",
        "what_was_not_shown": "This gate does not prove a constitutional agent; that remains preregistered ontology interpretation, not a verdict.",
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
