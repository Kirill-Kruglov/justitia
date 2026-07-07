#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, read_prereg, write_json

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

import artifacts  # noqa: E402
import atlas  # noqa: E402
import families  # noqa: E402

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
    seeds = [int(s) for s in thresholds["seeds"]]
    for policy15 in thresholds["validation_policy15"]:
        params = artifacts._clone_artifact_params(
            families.params_for("validation", policy15, "", scenario="validation"),
            artifact_channel="off",
            artifact_arm="A0",
        )
        for seed in seeds:
            rows.append(artifacts.run_one(seed, params, "validation", 0.0, policy15, "validation"))
    for world in thresholds["worlds"]:
        for policy15 in thresholds["boundary_policy15"]:
            params = artifacts.params_for_artifact_variant(
                BOUNDARY_POLICY_TO_VARIANT[policy15],
                world,
                scenario="boundary",
                artifact_arm="A0",
                adversarial_pressure=1.0,
            )
            for seed in seeds:
                rows.append(artifacts.run_one(seed, params, "adversarial_pressure", 1.0, "adversarial_pressure=1.00", "boundary"))
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
        atlas.BoundaryAtlasModel._score_c_no_consequence,
        families.AntiConcentrationVsConsequenceModel.choose_alloc,
        families.AntiConcentrationVsConsequenceModel._static_score_a,
        families.AntiConcentrationVsConsequenceModel._score_b,
        families.AntiConcentrationVsConsequenceModel._score_c,
        families.AntiConcentrationVsConsequenceModel._apply_cap,
    ]


def experiment() -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    expected = headline_expected_rows(thresholds)
    actual = run_headline_rows(thresholds)
    comparison = compare_rows(expected, actual)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N5a_artifact_default_equivalence", "role": "core", "seeds": len(thresholds["seeds"]), "pass_fail": "PASS"},
    ])
    decision = "PASS" if comparison["exact_equal"] and seed_report["admissible"] else "FAIL"
    write_json(OUTPUTS / "equivalence_checks.json", {
        "snapshot_summary": str(SNAPSHOT_SUMMARY),
        "comparison": comparison,
        "actual_summary_rows": actual,
    })
    return {
        "question": "Do artifact-channel neutral defaults exactly preserve committed J-G1 headline summary cells?",
        "mode": "engineering equivalence; not a scientific outcome",
        "metric": "Exact string equality for selected committed J-G1 summary.csv headline rows.",
        "preregistered_thresholds": thresholds,
        "decision": decision,
        "comparison": comparison,
        "seed_policy": seed_report,
        "downstream_consequence": "PASS permits J-N5/J-N5b preregistration; FAIL stops W8 until implementation is fixed and re-reviewed.",
        "fact": "artifact_channel=off and artifact_arm=A0 return through the published BoundaryAtlasModel path before any artifact emission or conformance code runs.",
        "inference": "Exact equality supports the engineering contract that the artifact channel is default-neutral.",
        "what_was_not_shown": "This gate does not evaluate A1/A2 or any non-default artifact-channel behavior.",
    }


def main() -> int:
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    taut = {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Engineering equivalence against committed J-G1 summary snapshot; no learned threshold.",
    }
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, experiment, leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
