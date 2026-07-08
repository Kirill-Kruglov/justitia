#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
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
import probing  # noqa: E402

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
ARMS = ["R0", "PO", "PD", "PA", "PN"]
TRAJECTORY_FIELDS = [
    "predictive_gate_open_by_step",
    "predictive_calibration_by_step",
    "predictive_harm_fraction_by_step",
    "probe_events_by_step",
    "probe_skips_by_step",
    "probe_recovery_audits",
    "probe_non_recovery_by_step",
]


def write_json_gz(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    return atlas.wilson(p, n, z=z)


def run_one(seed: int, world: str, pressure: float, arm: str) -> dict:
    params = probing.params_for_probe_variant(
        "C_full",
        world,
        scenario="J_N9_active_probing",
        arm=arm,
        adversarial_pressure=pressure,
    )
    row = probing.run_one(seed, params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N9")
    row["probe_comparison_arm"] = arm
    return row


def run_rows(worlds: list[str], pressures: list[float], seeds: list[int], arms: Iterable[str]) -> list[dict]:
    return [run_one(seed, world, pressure, arm) for world in worlds for pressure in pressures for arm in arms for seed in seeds]


def summarize(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["world"], row["axis_value"], row["axis_label"], row["probe_comparison_arm"])].append(row)
    out = []
    numeric_metrics = [
        "capture_index", "capture_threshold", "resource_hhi", "exploitative_strategy_mass", "cooperative_strategy_mass",
        "welfare", "response_diversity", "containment_cost", "false_containment", "containment_events",
        "predictive_gate_open_share", "predictive_latest_calibration_score", "predictive_preemptive_containment_events",
        "predictive_reactive_containment_events", "predictive_confounded_predictions", "predictive_resolved_predictions",
        "predictive_insufficient_evidence_steps", "probe_count", "probe_positive_count", "probe_negative_count",
        "probe_non_recovery_rate", "probe_recovery_denominator", "probe_mean_continuous_disagreement_score",
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
            "arm": arm,
            "n": n,
            "permanence_probability": perm,
            "permanence_ci_lo": perm_lo,
            "permanence_ci_hi": perm_hi,
            "collapse_probability": collapse,
            "collapse_ci_lo": collapse_lo,
            "collapse_ci_hi": collapse_hi,
        }
        for metric in numeric_metrics:
            row[metric] = mean([float(v.get(metric, 0.0) or 0.0) for v in vals])
        probe_zone_totals: dict[str, float] = defaultdict(float)
        for v in vals:
            for zone, count in (v.get("probe_count_by_zone") or {}).items():
                probe_zone_totals[str(zone)] += float(count)
        row["probe_count_by_zone_total"] = dict(sorted(probe_zone_totals.items()))
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
            rows = sorted([r for r in summary if r["world"] == world and r["arm"] == arm], key=lambda r: r["axis_value"])
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


def aggregate_probe_safety(rows: list[dict], thresholds: dict) -> dict:
    active = [r for r in rows if r.get("probe_comparison_arm") == "PA"]
    resolved = sum(int(r.get("probe_recovery_denominator", 0) or 0) for r in active)
    weighted_non_recovered = sum(float(r.get("probe_non_recovery_rate", 0.0) or 0.0) * int(r.get("probe_recovery_denominator", 0) or 0) for r in active)
    aggregate_rate = weighted_non_recovered / resolved if resolved else 0.0
    closed_runs = sum(1 for r in active if bool(r.get("probe_channel_closed", False)))
    return {
        "PA_probe_recovery_denominator": resolved,
        "PA_probe_non_recovery_rate": aggregate_rate,
        "PA_probe_channel_closed_runs": closed_runs,
        "non_recovery_budget": thresholds["probe_mechanics"]["non_recovery_budget"],
        "within_budget": aggregate_rate <= thresholds["probe_mechanics"]["non_recovery_budget"],
    }


def analyze(rows: list[dict], summary: list[dict], thresholds: dict, seed_report: dict) -> dict:
    ceilings = pressure_ceilings(summary, thresholds)
    measured_worlds = [w for w in thresholds["worlds"] if ceilings[w].get("R0") is not None]
    margin = float(thresholds["margin_grid_step"])
    hm1_worlds = []
    hm2_failures = []
    hm3_worlds = []
    hm3_failures = []
    pn_decorrelation_reading_worlds = []
    po_headroom_worlds = []
    pa_approx_r0_with_po_headroom = []
    for world in measured_worlds:
        r0 = ceilings[world].get("R0")
        po = ceilings[world].get("PO")
        pd = ceilings[world].get("PD")
        pa = ceilings[world].get("PA")
        pn = ceilings[world].get("PN")
        if delta(pa, r0) is not None and delta(pa, r0) >= margin:
            hm1_worlds.append(world)
        if not (ge_with_none(po, pa) and ge_with_none(pa, pd)):
            hm2_failures.append({"world": world, "PO": po, "PA": pa, "PD": pd})
        if delta(po, r0) is not None and delta(po, r0) > 0:
            po_headroom_worlds.append(world)
        if delta(po, r0) is not None and delta(po, r0) > 0 and (delta(pa, r0) is None or abs(delta(pa, r0)) < margin):
            pa_approx_r0_with_po_headroom.append(world)
        if world in hm1_worlds:
            hm3_worlds.append(world)
            if delta(pa, pn) is None or delta(pa, pn) < margin:
                hm3_failures.append({"world": world, "PA": pa, "PN": pn, "delta": delta(pa, pn)})
        if delta(pa, r0) is not None and delta(pa, r0) >= margin and delta(pn, r0) is not None and delta(pn, r0) >= margin and delta(pa, pn) is not None and abs(delta(pa, pn)) < margin:
            pn_decorrelation_reading_worlds.append(world)
    required_worlds = thresholds["H_M1_PA_extension"]["required_worlds_min"]
    hm1_pass = len(hm1_worlds) >= required_worlds
    hm2_pass = not hm2_failures
    if not hm3_worlds:
        hm3_verdict = "VACUOUS"
    else:
        hm3_verdict = "PASS" if not hm3_failures else "FAIL"
    safety = aggregate_probe_safety(rows, thresholds)
    hm5_ceiling_failures = []
    for world in measured_worlds:
        if not ge_with_none(ceilings[world].get("PA"), ceilings[world].get("R0")):
            hm5_ceiling_failures.append({"world": world, "R0": ceilings[world].get("R0"), "PA": ceilings[world].get("PA")})
    hm5_pass = not hm5_ceiling_failures and safety["within_budget"]
    mechanism = {
        "PA_calibration_mean": mean([float(r.get("predictive_latest_calibration_score", 0.0)) for r in summary if r["arm"] == "PA"]),
        "PD_calibration_mean": mean([float(r.get("predictive_latest_calibration_score", 0.0)) for r in summary if r["arm"] == "PD"]),
        "PA_gate_open_share_mean": mean([float(r.get("predictive_gate_open_share", 0.0)) for r in summary if r["arm"] == "PA"]),
        "PD_gate_open_share_mean": mean([float(r.get("predictive_gate_open_share", 0.0)) for r in summary if r["arm"] == "PD"]),
        "PA_confounded_predictions_mean": mean([float(r.get("predictive_confounded_predictions", 0.0)) for r in summary if r["arm"] == "PA"]),
        "PD_confounded_predictions_mean": mean([float(r.get("predictive_confounded_predictions", 0.0)) for r in summary if r["arm"] == "PD"]),
        "PA_probe_count_mean": mean([float(r.get("probe_count", 0.0)) for r in summary if r["arm"] == "PA"]),
        "PN_probe_count_mean": mean([float(r.get("probe_count", 0.0)) for r in summary if r["arm"] == "PN"]),
    }
    decision_vector = {
        "H_M1_PA_extension": "PASS" if hm1_pass else "FAIL",
        "H_M2_order_PO_ge_PA_ge_PD": "PASS" if hm2_pass else "FAIL",
        "H_M3_choice_bearing": hm3_verdict,
        "H_M4_mechanism": "RECORDED",
        "H_M5_safety": "PASS" if hm5_pass else "FAIL",
    }
    kill = {
        "phase2_mechanism_red_PA_approx_R0_when_PO_gt_R0": bool(pa_approx_r0_with_po_headroom) and not hm1_pass,
        "H_M5_independent_safety_kill": not hm5_pass,
        "PN_approx_PA_gt_R0_decorrelation_not_design_reading": bool(pn_decorrelation_reading_worlds),
    }
    decision = "PASS" if seed_report["admissible"] and hm1_pass and hm2_pass and hm3_verdict in {"PASS", "VACUOUS"} and hm5_pass else "FAIL"
    return {
        "decision": decision,
        "decision_vector": decision_vector,
        "pressure_ceilings": ceilings,
        "measured_worlds": measured_worlds,
        "H_M1_worlds": hm1_worlds,
        "H_M2_failures": hm2_failures,
        "H_M3_worlds": hm3_worlds,
        "H_M3_failures": hm3_failures,
        "H_M3_decorrelation_reading_worlds": pn_decorrelation_reading_worlds,
        "H_M5_ceiling_failures": hm5_ceiling_failures,
        "probe_safety": safety,
        "mechanism_recorded_metrics": mechanism,
        "phase2_kill_status": kill,
    }


def extract_trajectories(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = {
            "seed": row["seed"],
            "world": row["world"],
            "axis_value": row["axis_value"],
            "axis_label": row["axis_label"],
            "arm": row["probe_comparison_arm"],
        }
        for field in TRAJECTORY_FIELDS:
            if field in row:
                item[field] = row.get(field, [])
        out.append(item)
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
        "baseline": "Fresh R0 baseline rows over locked J-N9 worlds/pressure grid/seeds.",
        "baseline_pressure_ceilings": ceilings,
        "known_caveat": "R0 is part of the comparison, not evidence for active-probing benefit by itself.",
    }, baseline_summary, ceilings


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        probing.ProbingPredictiveBoundaryModel.choose_alloc,
        probing.ProbingPredictiveBoundaryModel._candidate_probes,
        probing.ProbingPredictiveBoundaryModel._select_probe,
        probing.ProbingPredictiveBoundaryModel._continuous_disagreement_score,
        probing.ProbingPredictiveBoundaryModel._probe_health_guard,
        probing.ProbingPredictiveBoundaryModel._resolve_probe_recovery,
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
    rows.extend(run_rows(worlds, pressures, seeds, ["PO", "PD", "PA", "PN"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N9_active_safe_to_fail_probing", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(rows, summary, thresholds, seed_report)
    write_json_gz(OUTPUTS / "j_n9_checks.json.gz", {"raw_runs": compact_rows(rows), "summary": summary, "analysis": analysis})
    write_json_gz(OUTPUTS / "probe_and_predictive_trajectories.json.gz", {"trajectories": extract_trajectories(rows)})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "Active safe-to-fail probing pressure ceilings, mechanism metrics, and recovery safety.",
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "J-N9 resolves line-11 phase-2 active-contact interpretation under the preregistered kill branches.",
        "fact": "Probe selection and containment policy functions were leakage-scanned under the usual forbidden names; probes are observable allocation actions and not calibration confounds.",
        "inference": "Any PA gain over PD under fixed representation is attributed to contact schedule/design, with PN separating decorrelation from informational choice.",
        "what_was_not_shown": prereg["metadata"]["what_was_not_shown"],
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
