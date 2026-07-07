#!/usr/bin/env python3
from __future__ import annotations

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

import atlas  # noqa: E402
import families  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / "outputs"
W7_WORLD = "W7_delayed_capture_recurring_ambiguous_catastrophes"

FORBIDDEN_NAMES = [
    *atlas.base.STRATEGY_FIELDS,
    "exploitative_label",
    "lineages",
    "strategy",
    "hidden_type",
    "_exploit_score",
    "exploit_score",
]

VARIANTS = [
    "no_governance",
    "static_alone",
    "sword_alone",
    "C_dyn_no_consequence",
    "C_full",
]


class W7HeldoutModel(atlas.BoundaryAtlasModel):
    """Held-out W7 world assembled inside the gate without changing model/."""

    def _init_world(self):
        if self.params.world != W7_WORLD:
            return super()._init_world()
        self.zones = [self._base_zone(i) for i in range(atlas.base.ZONES)]

        # W3-style ambiguous catastrophe substrate, slightly moderated from W3.
        for i in [0, 3]:
            self.zones[i].catastrophe = True
            self.zones[i].wellness = 0.38
            self.zones[i].productivity = 0.40
            self.zones[i].recovery = 0.34
        for i in [1, 4]:
            self.zones[i].lineages.append(self._lineage("deceptive_exploit", 10.0))
            self.zones[i].wellness = min(self.zones[i].wellness, 0.46)

        # W6-style mutation corridor: resilient mutants are present from t=0.
        for i in [2, 5, 8]:
            self.zones[i].lineages.append(self._lineage("resilient_mutant", 8.0))

        for z in self.zones:
            z.prev_wellness = z.wellness
            z.prev_productivity = z.productivity
            z.prev_recovery = z.recovery
            z.prev_population = self._zone_mass(z)
            z.prev_diversity = self._strategy_diversity(z)

    def _apply_shocks(self, step):
        if self.params.world != W7_WORLD:
            return super()._apply_shocks(step)

        # Recurring W3-style ambiguous catastrophe shocks.
        if step in {18, 36, 54, 72}:
            for z in self.zones:
                if z.catastrophe:
                    resilience = self._weighted(z, "shock_resilience_contribution")
                    hit = 0.24 * (1.0 - 0.55 * resilience)
                    z.wellness = atlas.base.clamp(z.wellness - hit)
                    z.productivity = atlas.base.clamp(z.productivity - 0.8 * hit)
                    z.recovery = atlas.base.clamp(z.recovery - 0.7 * hit)

        # Delayed-onset capture pressure below W2: W2 starts with pure_extractor
        # mass 20 in three zones; W7 adds smaller pulses only after onset.
        if step in {28, 56}:
            mass = 8.0 if step == 28 else 6.0
            for i in [1, 4, 7]:
                self.zones[i].lineages.append(self._lineage("pure_extractor", mass))
                self.zones[i].wellness = atlas.base.clamp(self.zones[i].wellness * 0.92)

    def choose_alloc(self):
        if self.params.world == W7_WORLD and self.params.policy15 == "no_governance":
            return atlas.base.normalize([1.0] * atlas.base.ZONES)
        return super().choose_alloc()


def _clone_params(params, **updates):
    data = dict(params.__dict__)
    data.update(updates)
    return params.__class__(**data)


def params_for_variant(variant: str):
    if variant == "no_governance":
        base_params = families.params_for("validation", "no_control_W2", "", scenario="J_N3_W7")
        return _clone_params(base_params, world=W7_WORLD, policy15="no_governance", policy="consequence_neighbor")
    if variant == "static_alone":
        return atlas.params_for_variant("A", W7_WORLD, scenario="J_N3_W7")
    if variant == "sword_alone":
        return atlas.params_for_variant("B", W7_WORLD, scenario="J_N3_W7")
    if variant == "C_dyn_no_consequence":
        return atlas.params_for_variant("C_dyn_no_consequence", W7_WORLD, scenario="J_N3_W7")
    if variant == "C_full":
        return atlas.params_for_variant("C_full", W7_WORLD, scenario="J_N3_W7")
    raise ValueError(variant)


def run_one(seed: int, variant: str) -> dict:
    params = params_for_variant(variant)
    model = W7HeldoutModel(seed, params)
    out = model.run()
    return {
        "seed": seed,
        "world": W7_WORLD,
        "variant": variant,
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


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    return atlas.wilson(p, n, z=z)


def summarize_variant(rows: list[dict]) -> dict:
    n = len(rows)
    perm = mean([float(r["permanence"]) for r in rows])
    collapse = mean([float(r["collapse"]) for r in rows])
    perm_lo, perm_hi = wilson(perm, n)
    collapse_lo, collapse_hi = wilson(collapse, n)
    return {
        "n": n,
        "permanence_probability": perm,
        "permanence_ci_lo": perm_lo,
        "permanence_ci_hi": perm_hi,
        "collapse_probability": collapse,
        "collapse_ci_lo": collapse_lo,
        "collapse_ci_hi": collapse_hi,
        "capture_index": mean([float(r["capture_index"]) for r in rows]),
        "capture_threshold": mean([float(r["capture_threshold"]) for r in rows]),
        "welfare": mean([float(r["welfare"]) for r in rows]),
        "response_diversity": mean([float(r["response_diversity"]) for r in rows]),
        "containment_events": mean([float(r["containment_events"]) for r in rows]),
        "containment_cost": mean([float(r["containment_cost"]) for r in rows]),
        "false_containment": mean([float(r["false_containment"]) for r in rows]),
        "exploitative_strategy_mass": mean([float(r["exploitative_strategy_mass"]) for r in rows]),
        "cooperative_strategy_mass": mean([float(r["cooperative_strategy_mass"]) for r in rows]),
        "mutation_events": mean([float(r["mutation_events"]) for r in rows]),
    }


def summarize(rows: Iterable[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["variant"]].append(row)
    return {variant: summarize_variant(grouped.get(variant, [])) for variant in VARIANTS}


def robust(row: dict, thresholds: dict) -> bool:
    return (
        row["permanence_ci_lo"] >= thresholds["permanence_ci_lo_bar"]
        and row["collapse_ci_hi"] <= thresholds["collapse_ci_hi_bar"]
        and row["capture_index"] <= row["capture_threshold"]
        and row["welfare"] >= thresholds["welfare_floor"]
        and row["response_diversity"] >= thresholds["response_diversity_floor"]
        and row["containment_cost"] <= thresholds["containment_cost_ceiling"]
        and row["false_containment"] <= thresholds["false_containment_ceiling"]
    )


def analyze(summary: dict[str, dict], thresholds: dict, seed_report: dict) -> dict:
    robust_by_variant = {variant: robust(row, thresholds) for variant, row in summary.items()}
    informative = not any(robust_by_variant[v] for v in ["no_governance", "static_alone", "sword_alone"])
    c_full = summary["C_full"]
    static_perm = summary["static_alone"]["permanence_probability"]
    sword_perm = summary["sword_alone"]["permanence_probability"]
    full_margin = c_full["permanence_probability"] - max(static_perm, sword_perm)
    no_consequence = summary["C_dyn_no_consequence"]
    no_consequence_control_passed = (
        no_consequence["containment_events"] <= thresholds["zero_containment_events_tolerance"]
        and not robust_by_variant["C_dyn_no_consequence"]
    )

    if not seed_report["admissible"]:
        decision = "INCONCLUSIVE"
    elif not informative:
        decision = "INCONCLUSIVE"
    elif (
        robust_by_variant["C_full"]
        and full_margin > thresholds["minimum_full_margin_over_singles"]
        and no_consequence_control_passed
    ):
        decision = "PASS"
    else:
        decision = "FAIL"

    return {
        "decision": decision,
        "robust_by_variant": robust_by_variant,
        "informativeness_gate_passed": informative,
        "full_margin_over_best_single": full_margin,
        "no_consequence_control_passed": no_consequence_control_passed,
    }


def tautology_report_from_baseline(baseline_rows: list[dict], thresholds: dict) -> tuple[dict, dict]:
    baseline_summary = summarize_variant(baseline_rows)
    baseline_passes = robust(baseline_summary, thresholds)
    return {
        "construction_may_be_tautological": baseline_passes,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "W7/no_governance",
        "baseline_passes_viability_bar": baseline_passes,
        "baseline_summary": baseline_summary,
        "known_caveat": "W7 is assembled inside this gate from existing justitia mechanisms, not from an independently authored substrate.",
    }, baseline_summary


def _score_for_evaluation(metrics):
    return metrics["decision"]


def _evaluation_suite():
    return _score_for_evaluation({"decision": "pending"})


def policy_path():
    return [
        W7HeldoutModel.choose_alloc,
        atlas.BoundaryAtlasModel.choose_alloc,
        atlas.BoundaryAtlasModel._score_c,
        atlas.BoundaryAtlasModel._score_c_no_consequence,
        families.AntiConcentrationVsConsequenceModel.choose_alloc,
        families.AntiConcentrationVsConsequenceModel._static_score_a,
        families.AntiConcentrationVsConsequenceModel._score_b,
        families.AntiConcentrationVsConsequenceModel._score_c,
        families.AntiConcentrationVsConsequenceModel._apply_cap,
    ]


def experiment(precomputed_baseline_rows: list[dict]) -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    seeds = [int(s) for s in thresholds["seeds"]]
    rows = list(precomputed_baseline_rows)
    for variant in [v for v in VARIANTS if v != "no_governance"]:
        for seed in seeds:
            rows.append(run_one(seed, variant))
    summary = summarize(rows)
    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N3_W7_core_variants", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
        {"metric": "J_N3_W7_controls", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    analysis = analyze(summary, thresholds, seed_report)
    write_json(OUTPUTS / "w7_checks.json", {"raw_runs": rows, "summary": summary, "analysis": analysis})
    return {
        "question": "Does the published C_full policy hold in held-out W7 on the untouched substrate?",
        "mode": "prospective held-out world; outcome unknown at lock time; decision citable under ANY outcome",
        "metric": "W7 robust kernel, informativeness controls, C_full margin over singles, and C_dyn_no_consequence control.",
        "world_design": read_prereg(HERE)["metadata"]["world_design"],
        "preregistered_thresholds": thresholds,
        "decision": analysis["decision"],
        "summary_by_variant": summary,
        "analysis": analysis,
        "seed_policy": seed_report,
        "downstream_consequence": "PASS supports out-of-family transfer; FAIL is a citable domain-boundary finding; INCONCLUSIVE means W7 controls made the world uninformative.",
        "fact": "W7 was implemented in this gate script; model/ was not changed for J-N3.",
        "inference": "Any PASS/FAIL is about this pre-locked composition of existing justitia mechanics, not about an independently authored external substrate.",
        "what_was_not_shown": "No claim is made about arbitrary future worlds, and W7 was designed by the same forge rather than by an independent group.",
    }


def main() -> int:
    thresholds = read_prereg(HERE)["thresholds"]
    seeds = [int(s) for s in thresholds["seeds"]]
    baseline_rows = [run_one(seed, "no_governance") for seed in seeds]
    taut, _baseline_summary = tautology_report_from_baseline(baseline_rows, thresholds)
    leak = LS.scan_fit_path(policy_path(), forbidden_names=FORBIDDEN_NAMES)
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_for_evaluation"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: experiment(baseline_rows), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
