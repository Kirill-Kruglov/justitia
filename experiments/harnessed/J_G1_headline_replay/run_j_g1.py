#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from experiments.harnessed.common import MODEL, ROOT, copy_tree, ensure_imports, fnum, read_csv, read_prereg, run_command, write_json

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

import atlas  # noqa: E402
import families  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / "outputs"
SNAPSHOT = OUTPUTS / "model_results"

FORBIDDEN_NAMES = [
    *atlas.base.STRATEGY_FIELDS,
    "exploitative_label",
    "lineages",
    "strategy",
    "hidden_type",
    "_exploit_score",
    "exploit_score",
]

POLICY_PATH = [
    atlas.BoundaryAtlasModel.choose_alloc,
    atlas.BoundaryAtlasModel._score_c,
    atlas.BoundaryAtlasModel._score_c_no_consequence,
    families.AntiConcentrationVsConsequenceModel.choose_alloc,
    families.AntiConcentrationVsConsequenceModel._static_score_a,
    families.AntiConcentrationVsConsequenceModel._score_b,
    families.AntiConcentrationVsConsequenceModel._score_c,
    families.AntiConcentrationVsConsequenceModel._apply_cap,
]


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def tautology_report_from_summary(summary_rows: list[dict[str, str]], thresholds: dict) -> dict:
    baseline = [
        r for r in summary_rows
        if r["scenario"] == "validation" and r["policy15"] == "no_control_W2"
    ]
    baseline_passes = any(
        fnum(r["permanence_probability"]) >= thresholds["no_governance_baseline_viability_bar"]
        and fnum(r["collapse_probability"]) <= 0.0
        for r in baseline
    )
    return {
        "construction_may_be_tautological": baseline_passes,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "validation/no_control_W2",
        "baseline_passes_viability_bar": baseline_passes,
        "known_caveat": (
            "Named circularity caveat: diversity is partly both a policy target and "
            "a viability term, so diversity-support claims must be read as "
            "mechanism-specific rather than as an independent proof of general "
            "ecosystem richness."
        ),
    }


def run_full_study(smoke: bool) -> dict:
    if (MODEL / "results").exists():
        shutil.rmtree(MODEL / "results")
    args = [str(ROOT / "run.py")]
    if smoke:
        args.append("--smoke")
    return run_command(["python3", *args], ROOT, env={"PYTHONPATH": f"{ROOT}:{MODEL}"})


def copy_outputs() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    copy_tree(MODEL / "results", SNAPSHOT)


def indexed(rows: list[dict[str, str]], *keys: str) -> dict[tuple[str, ...], dict[str, str]]:
    return {tuple(r[k] for k in keys): r for r in rows}


def evaluate(summary: list[dict[str, str]], cg: list[dict[str, str]], manifest: dict, thresholds: dict) -> dict:
    summary_by = indexed(summary, "scenario", "world", "policy15", "axis", "axis_label")
    cg_by = indexed(cg, "world", "axis", "axis_label", "variant")
    checks: dict[str, dict] = {}
    tol = thresholds["permanence_tolerance"]

    for world, expected in thresholds["static_alone_permanence"].items():
        row = summary_by[("boundary", world, "anti_hhi_allocator", "adversarial_pressure", "adversarial_pressure=1.00")]
        actual = fnum(row["permanence_probability"])
        checks[f"static_alone_{world}"] = {"actual": actual, "expected": expected, "passed": abs(actual - expected) <= tol}

    for world, expected in thresholds["sword_alone_permanence_max"].items():
        row = summary_by[("boundary", world, "delayed_harm_throttle", "adversarial_pressure", "adversarial_pressure=1.00")]
        actual = fnum(row["permanence_probability"])
        checks[f"sword_alone_{world}"] = {"actual": actual, "expected_max": expected, "passed": actual <= expected + tol}

    for world, expected in thresholds["robust_kernel_default_permanence"].items():
        row = cg_by[(world, "default", "default", "C_full")]
        actual = fnum(row["permanence"])
        checks[f"robust_kernel_{world}"] = {"actual": actual, "expected": expected, "passed": abs(actual - expected) <= tol}

    for world in thresholds["negative_worlds_no_robust_kernel"]:
        rows = [
            r for r in summary
            if r["scenario"] == "boundary"
            and r["world"] == world
            and r["policy15"] == "anti_concentration_plus_delayed_harm_throttle"
            and r["axis"] == "adversarial_pressure"
            and r["axis_label"] == "adversarial_pressure=1.00"
        ]
        actual = fnum(rows[0]["permanence_probability"]) if rows else None
        checks[f"negative_world_{world}"] = {
            "actual": actual,
            "expected_max": thresholds["negative_world_permanence_max"],
            "passed": actual is not None and actual <= thresholds["negative_world_permanence_max"] + tol,
        }

    for world in thresholds["consequence_removed_worlds"]:
        row = cg_by[(world, "default", "default", "C_dyn_no_consequence")]
        checks[f"decoupled_zero_events_{world}"] = {
            "containment_events": fnum(row["containment_events"]),
            "permanence": fnum(row["permanence"]),
            "passed": fnum(row["containment_events"]) == 0.0 and fnum(row["permanence"]) == 0.0,
        }

    for world in thresholds["threshold_stable_worlds"]:
        row = next(r for r in manifest["threshold_stability"] if r["world"] == world)
        checks[f"threshold_stability_{world}"] = {
            "ac_cg_fraction": row["ac_cg_fraction"],
            "expected": thresholds["threshold_stability_fraction"],
            "passed": row["ac_cg_fraction"] >= thresholds["threshold_stability_fraction"],
        }

    validation = manifest["validation_checks"]
    runtime_integrity = thresholds["runtime_integrity_checks"]
    checks["runtime_integrity"] = {
        "checks": {k: validation.get(k) for k in runtime_integrity},
        "passed": all(bool(validation.get(k)) for k in runtime_integrity),
        "expected_pass_count": len(runtime_integrity),
    }

    seed_report = SP.enforce_seed_policy([
        {"metric": "J_G1_core_permanence", "role": "core", "seeds": int(thresholds["core_metric_seeds"]), "pass_fail": "PASS"},
        {"metric": "J_G1_threshold_stability", "role": "core", "seeds": int(thresholds["threshold_combinations"]), "pass_fail": "PASS"},
        {"metric": "J_G1_integrity_checks", "role": "auxiliary_check", "seeds": int(thresholds["core_metric_seeds"]), "pass_fail": "PASS"},
    ])

    passed = all(c["passed"] for c in checks.values()) and seed_report["admissible"]
    return {"checks": checks, "seed_policy": seed_report, "decision": "PASS" if passed else "FAIL"}


def experiment(smoke: bool) -> dict:
    run_info = run_full_study(smoke)
    if run_info["returncode"] != 0:
        write_json(OUTPUTS / "run_failure.json", run_info)
        return {
            "question": "Can the published justitia headline results be replayed under fallacy-cutter enforcement?",
            "decision": "FAIL",
            "run": run_info,
            "downstream_consequence": "Replay failed before metrics could be evaluated.",
            "fact": "The full study command returned a non-zero status.",
            "inference": "No headline replay claim is citable from this run.",
            "what_was_not_shown": "No scientific deviation can be inferred until the command failure is diagnosed.",
        }
    copy_outputs()
    thresholds = read_prereg(HERE)["thresholds"]
    summary = read_csv(SNAPSHOT / "raw" / "summary.csv")
    cg = read_csv(SNAPSHOT / "raw" / "cg_ablation.csv")
    manifest = json.loads((SNAPSHOT / "run_manifest.json").read_text(encoding="utf-8"))
    evaluated = evaluate(summary, cg, manifest, thresholds)
    write_json(OUTPUTS / "replay_checks.json", evaluated)
    write_json(OUTPUTS / "run_command.json", run_info)
    return {
        "question": "Can the published justitia headline results be replayed under fallacy-cutter enforcement?",
        "mode": "confirmatory replay of published thresholds, NOT discovery preregistration",
        "metric": "Published headline permanence, decoupling, stability, and integrity checks.",
        "preregistered_thresholds": thresholds,
        "decision": evaluated["decision"],
        "headline_checks": evaluated["checks"],
        "seed_policy": evaluated["seed_policy"],
        "downstream_consequence": "PASS preserves only the published replay claim; FAIL/INCONCLUSIVE is reported as a replay finding.",
        "fact": "The run command completed and replay checks were computed from regenerated model/results.",
        "inference": "Harness-valid PASS means the published thresholds replayed under the declared enforcement surface.",
        "what_was_not_shown": "This is not independent replication and does not make the original study discovery-preregistered.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="Exercise the wrapper on justitia smoke mode; not citable for J-G1.")
    args = ap.parse_args()
    thresholds = read_prereg(HERE)["thresholds"] if (HERE / "PREREG.json").exists() else {}
    leak = LS.scan_fit_path(POLICY_PATH, forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    taut = {"construction_may_be_tautological": False, "information_ratio": None}
    if not args.smoke and (SNAPSHOT / "raw" / "summary.csv").exists():
        taut = tautology_report_from_summary(read_csv(SNAPSHOT / "raw" / "summary.csv"), thresholds)
    decision = run_gate(HERE, lambda: experiment(args.smoke), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

