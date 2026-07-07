#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

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
RUN_STAMP = SNAPSHOT / "RUN_STAMP.json"

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


def run_study_step(smoke: bool, argv: list[str]) -> int:
    start = time.monotonic()
    run_info = run_full_study(smoke)
    duration = time.monotonic() - start
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    if run_info["returncode"] != 0:
        write_json(OUTPUTS / "run_failure.json", run_info)
        print("study run failed; see outputs/run_failure.json", file=sys.stderr)
        return int(run_info["returncode"] or 1)
    copy_outputs()
    stamp = {
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "smoke" if smoke else "full",
        "smoke": bool(smoke),
        "duration_seconds": duration,
        "argv": argv,
    }
    write_json(RUN_STAMP, stamp)
    write_json(OUTPUTS / "run_command.json", run_info)
    print(f"study snapshot written to {SNAPSHOT}")
    print(f"run stamp written to {RUN_STAMP}")
    return 0


def load_snapshot_for_gate(smoke: bool) -> tuple[dict, list[dict[str, str]], list[dict[str, str]], dict]:
    if not RUN_STAMP.exists():
        raise RuntimeError(
            f"missing {RUN_STAMP}; run `python3 {Path(__file__).as_posix()} --run-study"
            f"{' --smoke' if smoke else ''}` first"
        )
    stamp = json.loads(RUN_STAMP.read_text(encoding="utf-8"))
    if bool(stamp.get("smoke")) != bool(smoke):
        expected = "smoke" if smoke else "full"
        actual = "smoke" if stamp.get("smoke") else "full"
        raise RuntimeError(
            f"RUN_STAMP mode mismatch: expected {expected}, found {actual}; "
            f"rerun `python3 {Path(__file__).as_posix()} --run-study"
            f"{' --smoke' if smoke else ''}` first"
        )
    summary_path = SNAPSHOT / "raw" / "summary.csv"
    cg_path = SNAPSHOT / "raw" / "cg_ablation.csv"
    manifest_path = SNAPSHOT / "run_manifest.json"
    missing = [p for p in [summary_path, cg_path, manifest_path] if not p.exists()]
    if missing:
        raise RuntimeError(
            "snapshot is incomplete; missing "
            + ", ".join(str(p) for p in missing)
            + "; run --run-study first"
        )
    return stamp, read_csv(summary_path), read_csv(cg_path), json.loads(manifest_path.read_text(encoding="utf-8"))


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
        row = next(r for r in manifest["threshold_stability"] if r["world"] == world)
        checks[f"negative_world_type_none_{world}"] = {
            "none_fraction": row["none_fraction"],
            "expected": thresholds["negative_world_type_none_fraction"],
            "passed": row["none_fraction"] >= thresholds["negative_world_type_none_fraction"],
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


def evaluate_smoke(manifest: dict, thresholds: dict) -> dict:
    validation = manifest["validation_checks"]
    runtime_integrity = thresholds["runtime_integrity_checks"]
    checks = {
        "runtime_integrity": {
            "checks": {k: validation.get(k) for k in runtime_integrity},
            "passed": all(bool(validation.get(k)) for k in runtime_integrity),
            "expected_pass_count": len(runtime_integrity),
        },
        "smoke_mode": {"actual": bool(validation.get("smoke_mode")), "passed": bool(validation.get("smoke_mode"))},
    }
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_G1_smoke_integrity_checks", "role": "auxiliary_check", "seeds": int(manifest.get("num_runs", 0)), "pass_fail": "PASS"},
    ])
    passed = all(c["passed"] for c in checks.values())
    return {"checks": checks, "seed_policy": seed_report, "decision": "PASS" if passed else "FAIL"}


def analyze_snapshot(smoke: bool, stamp: dict, summary: list[dict[str, str]], cg: list[dict[str, str]], manifest: dict) -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    evaluated = evaluate_smoke(manifest, thresholds) if smoke else evaluate(summary, cg, manifest, thresholds)
    write_json(OUTPUTS / "replay_checks.json", evaluated)
    return {
        "question": "Can the published justitia headline results be replayed under fallacy-cutter enforcement?",
        "mode": "confirmatory replay of published thresholds, NOT discovery preregistration" + (" (SMOKE WRAPPER TEST ONLY)" if smoke else ""),
        "metric": "Published headline permanence, decoupling, stability, and integrity checks." if not smoke else "Smoke wrapper integrity checks only.",
        "preregistered_thresholds": thresholds,
        "run_stamp": stamp,
        "decision": evaluated["decision"],
        "headline_checks": evaluated["checks"],
        "seed_policy": evaluated["seed_policy"],
        "downstream_consequence": "PASS preserves only the published replay claim; FAIL/INCONCLUSIVE is reported as a replay finding." if not smoke else "Smoke decision is not citable and must not be committed.",
        "fact": "The gate analyzed a pre-existing outputs/model_results snapshot produced by --run-study.",
        "inference": "Harness-valid PASS means the published thresholds replayed under the declared enforcement surface." if not smoke else "Smoke PASS means only the wrapper path executed under the harness.",
        "what_was_not_shown": "This is not independent replication and does not make the original study discovery-preregistered.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="Exercise the wrapper on justitia smoke mode; not citable for J-G1.")
    ap.add_argument("--run-study", action="store_true", help="Run the justitia study and write outputs/model_results + RUN_STAMP.json; does not run the gate or write a decision.")
    args = ap.parse_args()
    if args.run_study:
        return run_study_step(args.smoke, sys.argv)

    try:
        stamp, summary, cg, manifest = load_snapshot_for_gate(args.smoke)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    thresholds = read_prereg(HERE)["thresholds"]
    taut = tautology_report_from_summary(summary, thresholds)
    leak = LS.scan_fit_path(POLICY_PATH, forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: analyze_snapshot(args.smoke, stamp, summary, cg, manifest), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
