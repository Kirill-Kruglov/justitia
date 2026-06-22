"""Fast, deterministic checks of the core findings.

These run a handful of seeded cells (each a 100-step, 9-zone simulation), so the
whole file finishes in a second or two. They encode the headline claims directly:
neither lever alone holds, and the structural limit cannot act without a
consequence trigger.
"""

import statistics

import atlas
import families

SEEDS = range(16000, 16010)


def _mean_permanence(params, seeds=SEEDS):
    return statistics.fmean(families.run_one(s, params)["permanence"] for s in seeds)


def test_runs_are_deterministic():
    p = families.params_for("C", "anti_concentration_plus_delayed_harm_throttle", "W6_mutation_corridor")
    assert families.run_one(16000, p)["permanence"] == families.run_one(16000, p)["permanence"]


def test_neither_lever_alone_holds():
    # In a robust world the combination reaches durable homeostasis; either lever
    # alone collapses. This is the premise of the whole study.
    world = "W6_mutation_corridor"
    c = _mean_permanence(families.params_for("C", "anti_concentration_plus_delayed_harm_throttle", world))
    a = _mean_permanence(families.params_for("A", "anti_hhi_allocator", world))
    b = _mean_permanence(families.params_for("B", "delayed_harm_throttle", world))
    assert c > 0.9
    assert a < 0.1
    assert b < 0.1


def test_structural_limit_cannot_act_without_consequence():
    # The BE result: remove the consequence trigger and the structural
    # anti-concentration lever never engages, so the world collapses.
    p = atlas.params_for_variant("C_dyn_no_consequence", "W6_mutation_corridor", scenario="cg_ablation")
    rows = [atlas.run_one(s, p) for s in SEEDS]
    assert statistics.fmean(r["containment_events"] for r in rows) == 0.0
    assert statistics.fmean(r["permanence"] for r in rows) == 0.0


def test_consequence_gated_limit_is_what_works():
    # Same dynamics anti-concentration, but with the consequence trigger present:
    # now it engages and homeostasis holds.
    p = atlas.params_for_variant("C_dyn_only", "W6_mutation_corridor", scenario="cg_ablation")
    rows = [atlas.run_one(s, p) for s in SEEDS]
    assert statistics.fmean(r["containment_events"] for r in rows) > 0.0
    assert statistics.fmean(r["permanence"] for r in rows) > 0.9
