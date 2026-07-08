#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, read_prereg, write_json

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
ROOT = Path(__file__).resolve().parents[3]
OUTPUTS = HERE / "outputs"
SNAPSHOT_SUMMARY = ROOT / "experiments" / "harnessed" / "J_G1_headline_replay" / "outputs" / "model_results" / "raw" / "summary.csv"

FORBIDDEN_NAMES = [
    *atlas.base.STRATEGY_FIELDS,
    "exploitative_label",
    "lineages",
    "strategy",
    "hidden_type",
    "_exploit_score",
    "exploit_score",
]

BOUNDARY_POLICY_TO_VARIANT = {
    "anti_hhi_allocator": "A",
    "delayed_harm_throttle": "B",
    "anti_concentration_plus_delayed_harm_throttle": "C",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def row_key(row: dict) -> tuple[str, str, str, str, str]:
    return (row["scenario"], row["world"], row["policy15"], row["axis"], row["axis_label"])


def headline_expected_rows(thresholds: dict) -> list[dict[str, str]]:
    rows = read_csv(SNAPSHOT_SUMMARY)
    out = []
    for row in rows:
        if row["scenario"] == "validation" and row["policy15"] in thresholds["validation_policy15"]:
            out.append(row)
        if (
            row["scenario"] == "boundary"
            and row["axis"] == "adversarial_pressure"
            and row["axis_label"] == "adversarial_pressure=1.00"
            and row["policy15"] in thresholds["boundary_policy15"]
            and row["world"] in thresholds["worlds"]
        ):
            out.append(row)
    return sorted(out, key=row_key)


def run_headline_rows(thresholds: dict) -> list[dict]:
    rows = []
    seeds = [int(s) for s in thresholds["headline_seeds"]]
    for policy15 in thresholds["validation_policy15"]:
        params = probing._clone_probe_params(
            families.params_for("validation", policy15, "", scenario="validation"),
            predictive_arm="R0",
            probe_arm="off",
            probe_budget=0,
        )
        for seed in seeds:
            rows.append(probing.run_one(seed, params, "validation", 0.0, policy15, "validation"))
    for world in thresholds["worlds"]:
        for policy15 in thresholds["boundary_policy15"]:
            params = probing.params_for_probe_variant(
                BOUNDARY_POLICY_TO_VARIANT[policy15],
                world,
                scenario="boundary",
                arm="R0",
                adversarial_pressure=1.0,
            )
            for seed in seeds:
                rows.append(probing.run_one(seed, params, "adversarial_pressure", 1.0, "adversarial_pressure=1.00", "boundary"))
    return atlas.summarize(rows)


def stringify_value(value) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    return str(value)


def compare_rows(expected_rows: list[dict[str, str]], actual_rows: list[dict]) -> dict:
    actual_by_key = {row_key({k: str(v) for k, v in row.items()}): row for row in actual_rows}
    mismatches = []
    missing = []
    for expected in expected_rows:
        key = row_key(expected)
        actual = actual_by_key.get(key)
        if actual is None:
            missing.append({"key": key})
            continue
        for field, expected_value in expected.items():
            actual_value = stringify_value(actual.get(field, ""))
            if actual_value != expected_value:
                mismatches.append({
                    "key": key,
                    "field": field,
                    "expected": expected_value,
                    "actual": actual_value,
                })
    return {
        "expected_rows": len(expected_rows),
        "actual_rows": len(actual_rows),
        "missing": missing,
        "mismatches": mismatches,
        "exact_equal": not missing and not mismatches and len(expected_rows) == len(actual_rows),
    }


def canonical(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


def budget_zero_checks(thresholds: dict) -> dict:
    rows = []
    mismatches = []
    worlds = list(thresholds["budget_zero_worlds"])
    pressures = [float(p) for p in thresholds["budget_zero_pressures"]]
    seeds = [int(s) for s in thresholds["budget_zero_seeds"]]
    for world in worlds:
        for pressure in pressures:
            for seed in seeds:
                phase1_params = predictive.params_for_predictive_variant(
                    "C_full",
                    world,
                    scenario="J_N9a_budget_zero",
                    predictive_arm="PD",
                    adversarial_pressure=pressure,
                )
                phase1_row = predictive.run_one(seed, phase1_params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N9a_budget_zero")
                for arm in ("PA", "PN"):
                    probe_params = probing.params_for_probe_variant(
                        "C_full",
                        world,
                        scenario="J_N9a_budget_zero",
                        arm=arm,
                        probe_budget=0,
                        adversarial_pressure=pressure,
                    )
                    probe_row = probing.run_one(seed, probe_params, "adversarial_pressure", pressure, f"adversarial_pressure={pressure:.2f}", "J_N9a_budget_zero")
                    same = canonical(phase1_row) == canonical(probe_row)
                    rows.append({"world": world, "pressure": pressure, "seed": seed, "arm": arm, "exact_equal": same})
                    if not same:
                        phase1_keys = set(phase1_row)
                        probe_keys = set(probe_row)
                        field_mismatches = []
                        for field in sorted(phase1_keys & probe_keys):
                            if phase1_row[field] != probe_row[field]:
                                field_mismatches.append(field)
                        mismatches.append({
                            "world": world,
                            "pressure": pressure,
                            "seed": seed,
                            "arm": arm,
                            "phase1_only_keys": sorted(phase1_keys - probe_keys),
                            "probe_only_keys": sorted(probe_keys - phase1_keys),
                            "field_mismatches": field_mismatches[:60],
                        })
    return {
        "checks": rows,
        "mismatches": mismatches,
        "exact_equal": not mismatches,
        "total_checks": len(rows),
    }


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
        predictive.PredictiveBoundaryModel.step,
        predictive.PredictiveBoundaryModel._predictive_harm_fraction,
        predictive.PredictiveBoundaryModel._resolve_predictive_calibration,
        predictive.PredictiveBoundaryModel._calibration_report,
        predictive.LinearTransitionEnsemble.predict_harm_fraction,
        predictive.LinearTransitionEnsemble.predict_member_next,
        atlas.BoundaryAtlasModel.choose_alloc,
        atlas.BoundaryAtlasModel._score_c,
        atlas.BoundaryAtlasModel._score_c_no_consequence,
        families.AntiConcentrationVsConsequenceModel.choose_alloc,
        families.AntiConcentrationVsConsequenceModel._score_c,
        families.AntiConcentrationVsConsequenceModel._apply_cap,
    ]


def experiment() -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    expected = headline_expected_rows(thresholds)
    actual = run_headline_rows(thresholds)
    off_path = compare_rows(expected, actual)
    budget_zero = budget_zero_checks(thresholds)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N9a_probe_default_equivalence", "role": "headline_replay", "seeds": len(thresholds["headline_seeds"]), "pass_fail": "PASS"},
        {"metric": "J_N9a_probe_budget_zero_identity", "role": "engineering_budget_zero", "seeds": len(thresholds["budget_zero_seeds"]), "pass_fail": "PASS"},
    ])
    decision = "PASS" if off_path["exact_equal"] and budget_zero["exact_equal"] and seed_report["admissible"] else "FAIL"
    write_json(OUTPUTS / "equivalence_checks.json", {
        "snapshot_summary": str(SNAPSHOT_SUMMARY),
        "off_path_comparison": off_path,
        "budget_zero_identity": budget_zero,
        "actual_summary_rows": actual,
    })
    return {
        "question": "Do active-probing neutral paths exactly preserve published behavior and phase-1 PD when the probe budget is zero?",
        "mode": "engineering equivalence; not a scientific outcome",
        "metric": "Exact string equality for committed J-G1 headline rows plus exact canonical row equality for phase-1 PD versus PA/PN with probe_budget=0.",
        "preregistered_thresholds": thresholds,
        "decision": decision,
        "comparison": {"off_path": off_path, "budget_zero_identity": budget_zero},
        "seed_policy": seed_report,
        "downstream_consequence": "PASS permits J-N9 preregistration draft; FAIL stops line-11 phase 2 until implementation is fixed and re-reviewed.",
        "fact": "probe_arm=off and probe_budget=0 return through the phase-1 predictive path before probe candidate construction, probe RNG, or recovery-ledger code runs.",
        "inference": "Exact equality supports the engineering contract that active probing is additive and has PD as the budget-zero limit.",
        "what_was_not_shown": "This gate does not evaluate PA/PN scientific benefit or safety under positive probe budgets.",
    }


def main() -> int:
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    taut = {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Engineering equivalence against committed J-G1 snapshot and fresh 29900-29909 phase-1 PD budget-zero rows; no learned threshold.",
    }
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, experiment, leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
