#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, mean, read_prereg, write_json

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

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


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        atlas.BoundaryAtlasModel.choose_alloc,
        atlas.BoundaryAtlasModel._score_c,
        atlas.BoundaryAtlasModel._score_c_no_consequence,
        families.AntiConcentrationVsConsequenceModel.choose_alloc,
        families.AntiConcentrationVsConsequenceModel._score_c,
        families.AntiConcentrationVsConsequenceModel._apply_cap,
    ]


def params_for(world: str, cfg: dict[str, Any]):
    return atlas.params_for_variant(
        "C_full",
        world,
        scenario="J_N4_five_dial_isolation",
        delay=int(cfg["t_obs"]),
        t_act=int(cfg["t_act"]),
        v_prop=float(cfg["v_prop"]),
        t_irrev=int(cfg["t_irrev"]),
        r_rec=float(cfg["r_rec"]),
    )


def run_cell(seed: int, world: str, cfg: dict[str, Any], hypothesis: str, group: str, point: str) -> dict[str, Any]:
    params = params_for(world, cfg)
    row = atlas.run_one(seed, params, hypothesis, 0.0, point, group)
    row.update({
        "hypothesis": hypothesis,
        "group": group,
        "point": point,
        "t_obs": int(cfg["t_obs"]),
        "t_act": int(cfg["t_act"]),
        "v_prop": float(cfg["v_prop"]),
        "t_irrev": int(cfg["t_irrev"]),
        "r_rec": float(cfg["r_rec"]),
    })
    return row


def config_label(cfg: dict[str, Any]) -> str:
    return (
        f"t_obs={int(cfg['t_obs'])};t_act={int(cfg['t_act'])};"
        f"v_prop={float(cfg['v_prop']):.2f};t_irrev={int(cfg['t_irrev'])};"
        f"r_rec={float(cfg['r_rec']):.2f}"
    )


def merged(base: dict[str, Any], **updates: Any) -> dict[str, Any]:
    out = dict(base)
    out.update(updates)
    return out


def h_a_cases(thresholds: dict) -> Iterable[tuple[str, dict[str, Any], str, str]]:
    base = thresholds["base_config"]
    for world in thresholds["worlds"]:
        for dial, spec in thresholds["h_a"]["dials"].items():
            for value in spec["ordered_values"]:
                cfg = merged(base, **{dial: value})
                yield world, cfg, dial, config_label(cfg)


def h_b_cases(thresholds: dict) -> Iterable[tuple[str, dict[str, Any], str, str]]:
    base = thresholds["base_config"]
    for world in thresholds["worlds"]:
        for group in thresholds["h_b"]["equal_sum_groups"]:
            name = group["name"]
            for pair in group["pairs"]:
                cfg = merged(base, t_obs=pair["t_obs"], t_act=pair["t_act"])
                yield world, cfg, name, config_label(cfg)


def h_c_cases(thresholds: dict) -> Iterable[tuple[str, dict[str, Any], str, str]]:
    base = thresholds["base_config"]
    for world in thresholds["worlds"]:
        for v_prop in thresholds["h_c"]["fixed_v_prop"]:
            for r_rec in thresholds["h_c"]["fixed_r_rec"]:
                for group in thresholds["h_c"]["equal_ratio_groups"]:
                    name = f"{group['name']};v_prop={float(v_prop):.2f};r_rec={float(r_rec):.2f}"
                    for pair in group["pairs"]:
                        cfg = merged(
                            base,
                            t_obs=pair["T_response"],
                            t_act=0,
                            t_irrev=pair["t_irrev"],
                            v_prop=v_prop,
                            r_rec=r_rec,
                        )
                        yield world, cfg, name, config_label(cfg)


def run_grid(thresholds: dict) -> list[dict[str, Any]]:
    seeds = [int(s) for s in thresholds["seeds"]]
    rows = []
    for hypothesis, cases in [
        ("H-A", h_a_cases(thresholds)),
        ("H-B", h_b_cases(thresholds)),
        ("H-C", h_c_cases(thresholds)),
    ]:
        for world, cfg, group, point in cases:
            for seed in seeds:
                rows.append(run_cell(seed, world, cfg, hypothesis, group, point))
    return rows


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    keys = ("hypothesis", "world", "group", "point", "t_obs", "t_act", "v_prop", "t_irrev", "r_rec")
    for row in rows:
        grouped[tuple(row[k] for k in keys)].append(row)
    out = []
    for key, vals in sorted(grouped.items()):
        row = {k: key[i] for i, k in enumerate(keys)}
        row["n"] = len(vals)
        row["permanence_probability"] = mean([float(v["permanence"]) for v in vals])
        row["collapse_probability"] = mean([float(v["collapse"]) for v in vals])
        row["capture_index"] = mean([float(v["capture_index"]) for v in vals])
        row["welfare"] = mean([float(v["welfare"]) for v in vals])
        row["exploitative_strategy_mass"] = mean([float(v["exploitative_strategy_mass"]) for v in vals])
        row["false_containment"] = mean([float(v["false_containment"]) for v in vals])
        out.append(row)
    return out


def analyze_h_a(cells: list[dict[str, Any]], thresholds: dict) -> dict[str, Any]:
    tol = thresholds["h_a"]["monotonicity_tolerance"]
    violations = []
    for world in thresholds["worlds"]:
        for dial, spec in thresholds["h_a"]["dials"].items():
            ordered = spec["ordered_values"]
            direction = spec["expected_direction_along_order"]
            points = []
            for value in ordered:
                row = next(
                    r for r in cells
                    if r["hypothesis"] == "H-A" and r["world"] == world and r["group"] == dial and r[dial] == value
                )
                points.append(row)
            for prev, curr in zip(points, points[1:]):
                prev_p = float(prev["permanence_probability"])
                curr_p = float(curr["permanence_probability"])
                if direction == "nonincreasing" and curr_p > prev_p + tol:
                    violations.append({"world": world, "dial": dial, "from": prev["point"], "to": curr["point"], "from_perm": prev_p, "to_perm": curr_p})
                if direction == "nondecreasing" and curr_p < prev_p - tol:
                    violations.append({"world": world, "dial": dial, "from": prev["point"], "to": curr["point"], "from_perm": prev_p, "to_perm": curr_p})
    return {"verdict": "PASS" if not violations else "FAIL", "violations": violations}


def spread(rows: list[dict[str, Any]]) -> float:
    vals = [float(r["permanence_probability"]) for r in rows]
    return max(vals) - min(vals) if vals else 0.0


def analyze_h_b(cells: list[dict[str, Any]], thresholds: dict) -> dict[str, Any]:
    tol = thresholds["h_b"]["equal_sum_tolerance"]
    violations = []
    for world in thresholds["worlds"]:
        for group in thresholds["h_b"]["equal_sum_groups"]:
            rows = [r for r in cells if r["hypothesis"] == "H-B" and r["world"] == world and r["group"] == group["name"]]
            s = spread(rows)
            if len(rows) != len(group["pairs"]) or s > tol:
                violations.append({"world": world, "group": group["name"], "spread": s, "rows": len(rows)})
    return {"verdict": "PASS" if not violations else "FAIL", "violations": violations}


def analyze_h_c(cells: list[dict[str, Any]], thresholds: dict) -> dict[str, Any]:
    tol = thresholds["h_c"]["equal_ratio_tolerance"]
    violations = []
    for world in thresholds["worlds"]:
        for v_prop in thresholds["h_c"]["fixed_v_prop"]:
            for r_rec in thresholds["h_c"]["fixed_r_rec"]:
                for group in thresholds["h_c"]["equal_ratio_groups"]:
                    name = f"{group['name']};v_prop={float(v_prop):.2f};r_rec={float(r_rec):.2f}"
                    rows = [r for r in cells if r["hypothesis"] == "H-C" and r["world"] == world and r["group"] == name]
                    s = spread(rows)
                    if len(rows) != len(group["pairs"]) or s > tol:
                        violations.append({"world": world, "group": name, "spread": s, "rows": len(rows)})
    return {"verdict": "PASS" if not violations else "FAIL", "violations": violations}


def vector_decision(analysis: dict[str, Any], seed_report: dict[str, Any]) -> str:
    if not seed_report["admissible"]:
        return "INCONCLUSIVE"
    verdicts = [analysis[h]["verdict"] for h in ["H-A", "H-B", "H-C"]]
    if all(v == "PASS" for v in verdicts):
        return "PASS"
    if any(v == "FAIL" for v in verdicts):
        return "FAIL"
    return "INCONCLUSIVE"


def experiment() -> dict[str, Any]:
    thresholds = read_prereg(HERE)["thresholds"]
    rows = run_grid(thresholds)
    cells = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N4_H_A_directionality", "role": "core", "seeds": len(thresholds["seeds"]), "pass_fail": "PASS"},
        {"metric": "J_N4_H_B_equal_response_sum", "role": "core", "seeds": len(thresholds["seeds"]), "pass_fail": "PASS"},
        {"metric": "J_N4_H_C_ratio_sufficiency", "role": "core", "seeds": len(thresholds["seeds"]), "pass_fail": "PASS"},
    ])
    analysis = {
        "H-A": analyze_h_a(cells, thresholds),
        "H-B": analyze_h_b(cells, thresholds),
        "H-C": analyze_h_c(cells, thresholds),
    }
    decision = vector_decision(analysis, seed_report)
    write_json(OUTPUTS / "five_dial_checks.json", {
        "raw_runs": rows,
        "cells": cells,
        "analysis": analysis,
    })
    return {
        "question": "Which five-dial speed-limit hypotheses survive isolated prospective testing?",
        "mode": "prospective; outcome unknown at lock time; decision vector citable under ANY outcome",
        "metric": "Permanence-probability directionality, equal-response-sum spread, and equal-ratio spread.",
        "preregistered_thresholds": thresholds,
        "decision": decision,
        "hypothesis_verdicts": {h: analysis[h]["verdict"] for h in ["H-A", "H-B", "H-C"]},
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "Each hypothesis verdict is citable independently; FAIL is a boundary finding, not a tuning request.",
        "fact": "The gate uses the post-J-N4a substrate dials after exact default-equivalence passed.",
        "inference": "The vector tests directionality, t_obs/t_act symmetry, and ratio sufficiency only under the preregistered grids.",
        "what_was_not_shown": "This is not an exhaustive continuous surface map; exploratory surfaces remain non-citable unless separately preregistered.",
    }


def main() -> int:
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    taut = {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Prospective five-dial factorial grid; thresholds and equal-ratio groups are locked before execution.",
    }
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, experiment, leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    print(f"hypothesis verdicts: {decision['hypothesis_verdicts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
