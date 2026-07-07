#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import sys
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
import predictive  # noqa: E402
from experiments.harnessed.J_N3_heldout_W7 import run_j_n3 as jn3  # noqa: E402

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
ARMS = ["R0", "PO", "PD"]
TRAJECTORY_FIELDS = ["predictive_gate_open_by_step", "predictive_calibration_by_step", "predictive_harm_fraction_by_step"]


class PredictiveW7Model(jn3.W7HeldoutModel, predictive.PredictiveBoundaryModel):
    """J-N3 W7 imported unchanged, with predictive referee layered by MRO."""



def write_json_gz(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def clone_predictive_params(params, arm: str):
    return predictive._clone_predictive_params(params, predictive_arm=arm)


def run_one(seed: int, arm: str) -> dict:
    params = clone_predictive_params(jn3.params_for_variant("C_full"), arm)
    model = PredictiveW7Model(seed, params)
    out = model.run()
    row = {
        "seed": seed,
        "world": jn3.W7_WORLD,
        "predictive_arm": arm,
        "family": params.family,
        "policy15": params.policy15,
        "policy": params.policy,
        "delay": params.delay,
        "t_irrev": params.t_irrev,
        "capture_threshold": params.capture_threshold,
        "mutation_rate": params.mutation_rate,
        "containment_timer_activity": sum(z.containment_timer for z in model.zones),
        **out,
    }
    row.update(model.predictive_metrics())
    return row


def run_rows(seeds: list[int], arms: Iterable[str]) -> list[dict]:
    return [run_one(seed, arm) for arm in arms for seed in seeds]


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    return atlas.wilson(p, n, z=z)


def summarize_arm(rows: list[dict]) -> dict:
    n = len(rows)
    perm = mean([float(r["permanence"]) for r in rows])
    collapse = mean([float(r["collapse"]) for r in rows])
    perm_lo, perm_hi = wilson(perm, n)
    collapse_lo, collapse_hi = wilson(collapse, n)
    row = {
        "n": n,
        "permanence_probability": perm,
        "permanence_ci_lo": perm_lo,
        "permanence_ci_hi": perm_hi,
        "collapse_probability": collapse,
        "collapse_ci_lo": collapse_lo,
        "collapse_ci_hi": collapse_hi,
    }
    for metric in [
        "capture_index", "capture_threshold", "welfare", "response_diversity", "containment_events",
        "containment_cost", "false_containment", "exploitative_strategy_mass", "cooperative_strategy_mass",
        "mutation_events", "predictive_gate_open_share", "predictive_latest_calibration_score",
        "predictive_preemptive_containment_events", "predictive_reactive_containment_events",
        "predictive_confounded_predictions", "predictive_resolved_predictions", "predictive_insufficient_evidence_steps",
    ]:
        row[metric] = mean([float(r.get(metric, 0.0)) for r in rows])
    return row


def summarize(rows: list[dict]) -> dict[str, dict]:
    return {arm: summarize_arm([r for r in rows if r["predictive_arm"] == arm]) for arm in sorted({r["predictive_arm"] for r in rows})}


def analyze(summary: dict[str, dict], thresholds: dict, seed_report: dict) -> dict:
    h = thresholds["H_L5_W7_specificity"]
    r0_false = summary["R0"]["false_containment"]
    pd = summary["PD"]
    po = summary["PO"]
    pd_pass = pd["false_containment"] <= h["false_containment_max"] and pd["permanence_probability"] >= h["permanence_min"]
    po_pass = po["false_containment"] <= h["false_containment_max"] and po["permanence_probability"] >= h["permanence_min"]
    directional = r0_false - pd["false_containment"]
    decision = "PASS" if seed_report["admissible"] and pd_pass else "FAIL"
    return {
        "decision": decision,
        "decision_vector": {
            "H_L5_W7_specificity_PD": "PASS" if pd_pass else "FAIL",
            "PO_upper_bound_W7": "PASS" if po_pass else "FAIL",
            "directional_delta_R0_minus_PD": directional,
            "directional_delta_ge_0_10": directional >= h["recorded_directional_delta_min"],
        },
        "R0_false_containment": r0_false,
        "PD_false_containment": pd["false_containment"],
        "PO_false_containment": po["false_containment"],
        "PD_permanence": pd["permanence_probability"],
        "PO_permanence": po["permanence_probability"],
        "directional_delta_R0_minus_PD": directional,
        "gate_activity_by_arm": {arm: row.get("predictive_gate_open_share", 0.0) for arm, row in summary.items()},
    }


def extract_trajectories(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        if row["predictive_arm"] == "R0":
            continue
        out.append({
            "seed": row["seed"],
            "world": row["world"],
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


def tautology_report_from_r0(baseline_rows: list[dict]) -> tuple[dict, dict]:
    baseline_summary = summarize_arm(baseline_rows)
    return {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Fresh W7 R0 baseline rows over locked J-N8b seeds.",
        "baseline_summary": baseline_summary,
        "known_caveat": "R0 is the imported W7 C_full baseline, not evidence for predictive benefit by itself.",
    }, baseline_summary


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        PredictiveW7Model.choose_alloc,
        predictive.PredictiveBoundaryModel.choose_alloc,
        predictive.PredictiveBoundaryModel._predictive_harm_fraction,
        predictive.PredictiveBoundaryModel._resolve_predictive_calibration,
        predictive.PredictiveBoundaryModel._calibration_report,
        predictive.LinearTransitionEnsemble.predict_harm_fraction,
        predictive.LinearTransitionEnsemble.predict_member_next,
        predictive.ShadowOracleForecaster.predict_harm_fraction,
        jn3.W7HeldoutModel.choose_alloc,
    ]


def experiment(precomputed_r0_rows: list[dict]) -> dict:
    prereg = read_prereg(HERE)
    thresholds = prereg["thresholds"]
    seeds = [int(s) for s in thresholds["seeds"]]
    rows = list(precomputed_r0_rows)
    rows.extend(run_rows(seeds, ["PO", "PD"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N8b_W7_predictive_referee", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(summary, thresholds, seed_report)
    write_json_gz(OUTPUTS / "j_n8b_checks.json.gz", {"raw_runs": compact_rows(rows), "summary": summary, "analysis": analysis})
    write_json_gz(OUTPUTS / "predictive_trajectories.json.gz", {"trajectories": extract_trajectories(rows)})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "W7 R0 vs PD/PO predictive false containment and permanence under imported J-N3 W7.",
        "world_reuse_contract": prereg["metadata"]["world_reuse_contract"],
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "summary_by_arm": summary,
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "H-L5 combines with J-N8 kill interpretation for line-11 phase 1.",
        "fact": "W7 is imported from experiments.harnessed.J_N3_heldout_W7.run_j_n3; this runner does not copy or edit the world definition.",
        "inference": "Any specificity improvement is attributed only through the preregistered predictive self-gated mechanism.",
        "what_was_not_shown": "No claim is made about W7 variants or active probing in this gate.",
    }


def main() -> int:
    thresholds = read_prereg(HERE)["thresholds"]
    seeds = [int(s) for s in thresholds["seeds"]]
    baseline_rows = run_rows(seeds, ["R0"])
    taut, _baseline_summary = tautology_report_from_r0(baseline_rows)
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: experiment(baseline_rows), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
