#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
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

ARM_TO_CHANNEL = {"A0": "off", "A2f": "verified", "A2s": "verified"}
TRAJECTORY_FIELDS = ["declared_mass_by_step", "stiffness_by_step", "binding_events_by_step"]


class ArtifactW7Model(jn3.W7HeldoutModel, artifacts.ArtifactBoundaryModel):
    """J-N3 W7 imported unchanged, with seeded artifact policy layered by MRO."""



def clone_artifact_params(params, arm: str):
    return artifacts._clone_artifact_params(params, artifact_channel=ARM_TO_CHANNEL[arm], artifact_arm=arm)


def run_one(seed: int, arm: str) -> dict:
    params = clone_artifact_params(jn3.params_for_variant("C_full"), arm)
    model = ArtifactW7Model(seed, params)
    out = model.run()
    row = {
        "seed": seed,
        "world": jn3.W7_WORLD,
        "artifact_arm": arm,
        "artifact_channel": ARM_TO_CHANNEL[arm],
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
    if ARM_TO_CHANNEL[arm] != "off":
        row.update(model.artifact_adoption_metrics())
    return row


def run_rows(seeds: list[int], arms: Iterable[str]) -> list[dict]:
    return [run_one(seed, arm) for arm in arms for seed in seeds]


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = max(0.0, min(1.0, p))
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


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
        "capture_index",
        "capture_threshold",
        "welfare",
        "response_diversity",
        "containment_events",
        "containment_cost",
        "false_containment",
        "exploitative_strategy_mass",
        "cooperative_strategy_mass",
        "mutation_events",
        "mean_declared_share",
        "max_declared_share",
        "last_quarter_declared_share",
        "mean_declared_stiffness",
        "counterfactual_nonconformance_rate",
        "realized_nonconformance_rate",
        "envelope_binding",
    ]:
        row[metric] = mean([float(r.get(metric, 0.0)) for r in rows])
    for metric in ["declared_zone_steps", "nonconforming_declared_zone_steps"]:
        row[metric] = sum(int(r.get(metric, 0)) for r in rows)
    return row


def summarize(rows: list[dict]) -> dict[str, dict]:
    return {arm: summarize_arm([r for r in rows if r["artifact_arm"] == arm]) for arm in sorted({r["artifact_arm"] for r in rows})}


def analyze(summary: dict[str, dict], thresholds: dict, seed_report: dict) -> dict:
    h = thresholds["H_S4_W7_seeded_specificity_revenge"]
    a2f = summary["A2f"]
    h4 = a2f["false_containment"] <= h["A2f_false_containment_max"] and a2f["permanence_probability"] >= h["A2f_permanence_min"]
    delta_false = summary["A0"]["false_containment"] - a2f["false_containment"]
    return {
        "decision": "PASS" if seed_report["admissible"] and h4 else "FAIL",
        "decision_vector": {"H_S4_W7_seeded_specificity_revenge": "PASS" if h4 else "FAIL"},
        "false_containment_delta_A0_minus_A2f": delta_false,
        "A0_false_containment": summary["A0"]["false_containment"],
        "A2f_false_containment": a2f["false_containment"],
        "A2f_permanence": a2f["permanence_probability"],
        "A2s_recorded": summary.get("A2s", {}),
    }


def extract_trajectories(rows: list[dict]) -> list[dict]:
    trajectories = []
    for row in rows:
        if row["artifact_channel"] == "off":
            continue
        trajectories.append({
            "seed": row["seed"],
            "world": row["world"],
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


def tautology_report_from_a0(baseline_rows: list[dict]) -> tuple[dict, dict]:
    baseline_summary = summarize_arm(baseline_rows)
    return {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Fresh W7 A0 baseline rows over locked J-N6b seeds.",
        "baseline_summary": baseline_summary,
        "known_caveat": "A0 is the imported W7 baseline, not evidence for seeded artifact benefit by itself.",
    }, baseline_summary


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        ArtifactW7Model.choose_alloc,
        artifacts.ArtifactBoundaryModel.choose_alloc,
        artifacts.ArtifactBoundaryModel._artifact_bad_consequence,
        artifacts.artifact_conforms,
    ]


def experiment(precomputed_a0_rows: list[dict]) -> dict:
    prereg = read_prereg(HERE)
    thresholds = prereg["thresholds"]
    seeds = [int(s) for s in thresholds["seeds"]]
    rows = list(precomputed_a0_rows)
    rows.extend(run_rows(seeds, ["A2f", "A2s"]))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N6b_W7_seeded_adoption", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(summary, thresholds, seed_report)
    write_json(OUTPUTS / "j_n6b_checks.json", {"raw_runs": compact_rows(rows), "summary": summary, "analysis": analysis})
    write_json(OUTPUTS / "adoption_stiffness_trajectories.json", {"trajectories": extract_trajectories(rows)})
    return {
        "question": prereg["metadata"]["question"],
        "mode": prereg["metadata"]["mode"],
        "metric": "W7 A0 vs A2f false containment and permanence under imported J-N3 W7; A2s recorded alongside.",
        "world_reuse_contract": prereg["metadata"]["world_reuse_contract"],
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "decision_vector": analysis["decision_vector"],
        "summary_by_arm": summary,
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "H-S4 combines with J-N6 H-S1 for the FW-2b kill simpliciter.",
        "fact": "W7 is imported from experiments.harnessed.J_N3_heldout_W7.run_j_n3; this runner does not copy or edit the world definition.",
        "inference": "A2s is recorded for adoption/stiffness comparison but H-S4 is evaluated on the preregistered primary arm A2f.",
        "what_was_not_shown": "No claim is made about W7 variants or non-W7 worlds in this gate.",
    }


def main() -> int:
    thresholds = read_prereg(HERE)["thresholds"]
    seeds = [int(s) for s in thresholds["seeds"]]
    baseline_rows = run_rows(seeds, ["A0"])
    taut, _baseline_summary = tautology_report_from_a0(baseline_rows)
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: experiment(baseline_rows), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
