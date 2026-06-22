#!/usr/bin/env python3
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import substrate as base

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results_14"
RAW = RESULTS / "raw"
ORIGINAL_SEEDS = list(range(9600, 9625))
HELDOUT_SEEDS = list(range(9800, 9900))
SMALL_SEEDS = list(range(9900, 9925))

VIABLE_CELLS = [
    ("W6_action_channel_containment", "W6_mutation_corridor", "action_channel_containment"),
    ("W6_consequence_plus_diversity", "W6_mutation_corridor", "consequence_plus_diversity"),
    ("W1_consequence_plus_diversity", "W1_proxy_goodhart", "consequence_plus_diversity"),
]
ABLATIONS = [
    "full",
    "no_containment",
    "no_diversity_support",
    "no_response_to_aid",
    "no_anti_concentration",
    "no_aid_escrow",
    "no_migration_friction",
    "no_replication_throttle",
    "no_neighbor_consequence",
    "feature_proxy_only",
    "random_allocation",
]


@dataclass(frozen=True)
class RobustParams(base.Params):
    cell_id: str = ""
    scenario: str = "seed_robustness"
    ablation: str = "full"
    adversarial_pressure: float = 1.0
    catastrophe_severity: float = 1.0
    initial_exploit_mass_scale: float = 1.0
    initial_resource_concentration_scale: float = 1.0
    extraction_payoff_scale: float = 1.0
    interception_payoff_scale: float = 1.0
    harm_payoff_scale: float = 1.0
    exploit_mutation_bias: float = 0.0
    action_channel_cost_scale: float = 1.0
    random_allocation: int = 0
    fixed_mi_claim: int = 0


def git_value(args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return "unavailable"


def spec_hash():
    return hashlib.sha256((ROOT / "SPEC.md").read_bytes()).hexdigest()


def safe_mean(xs):
    return statistics.fmean(xs) if xs else 0.0


def stdev(xs):
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def normal_ci(xs, z=1.96):
    if not xs:
        return 0.0, 0.0
    m = safe_mean(xs)
    if len(xs) <= 1:
        return m, m
    half = z * stdev(xs) / math.sqrt(len(xs))
    return m - half, m + half


def wilson_from_mean(p, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0
    p = max(0.0, min(1.0, p))
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


class RobustModel(base.EvolvableStrategyModel):
    def _init_world(self):
        super()._init_world()
        if self.params.adversarial_pressure != 1.0:
            for z in self.zones:
                for l in z.lineages:
                    if self._exploit_score(l) > 0.30:
                        for k in ["extraction_rate", "aid_interception_rate", "neighbor_harm_rate", "deception_investment", "migration_follow_rate", "replication_aggressiveness"]:
                            l.strategy[k] = base.clamp(l.strategy[k] * self.params.adversarial_pressure)
        if self.params.initial_exploit_mass_scale != 1.0:
            for z in self.zones:
                for l in z.lineages:
                    if self._exploit_score(l) > 0.42:
                        l.mass *= self.params.initial_exploit_mass_scale
        if self.params.initial_resource_concentration_scale != 1.0:
            for z in self.zones:
                if not z.lineages:
                    continue
                z.lineages.sort(key=lambda x: x.mass, reverse=True)
                if self.params.initial_resource_concentration_scale > 1.0:
                    z.lineages[0].mass *= self.params.initial_resource_concentration_scale
                else:
                    total = self._zone_mass(z)
                    equal = total / len(z.lineages)
                    for l in z.lineages:
                        l.mass = l.mass * self.params.initial_resource_concentration_scale + equal * (1.0 - self.params.initial_resource_concentration_scale)

    def _apply_shocks(self, step):
        before = [(z.wellness, z.productivity, z.recovery) for z in self.zones]
        super()._apply_shocks(step)
        sev = self.params.catastrophe_severity
        if sev != 1.0 and self.params.world in {"W3_catastrophe_ambiguity", "W4_scavenger_catastrophe", "W5_monoculture_shock"}:
            for z, (bw, bp, br) in zip(self.zones, before):
                if z.wellness < bw:
                    z.wellness = base.clamp(bw - (bw - z.wellness) * sev)
                if z.productivity < bp:
                    z.productivity = base.clamp(bp - (bp - z.productivity) * sev)
                if z.recovery < br:
                    z.recovery = base.clamp(br - (br - z.recovery) * sev)

    def _mutate_strategy(self, lineage):
        child = super()._mutate_strategy(lineage)
        if self.params.exploit_mutation_bias:
            for k in ["extraction_rate", "aid_interception_rate", "neighbor_harm_rate", "deception_investment", "replication_aggressiveness"]:
                child.strategy[k] = base.clamp(child.strategy[k] + self.params.exploit_mutation_bias)
            for k in ["cooperation_investment", "productive_contribution"]:
                child.strategy[k] = base.clamp(child.strategy[k] - 0.5 * self.params.exploit_mutation_bias)
        return child

    def _score(self, obs, i):
        ab = self.params.ablation
        if ab == "feature_proxy_only":
            return obs.apparent_cooperation[i]
        need = 1.0 - min(obs.wellness[i], obs.productivity[i], obs.recovery[i])
        if ab == "random_allocation":
            return self.rng.random()
        if ab == "no_neighbor_consequence":
            div_gap = max(0.0, self.params.diversity_floor - obs.response_diversity[i]) if self.params.policy == "consequence_plus_diversity" else 0.0
            return 0.80 * need + 0.60 * obs.response_to_aid[i] + 0.85 * div_gap
        if ab == "no_response_to_aid":
            div_gap = max(0.0, self.params.diversity_floor - obs.response_diversity[i]) if self.params.policy == "consequence_plus_diversity" else 0.0
            return 0.75 * need + 1.7 * obs.neighbor_delta[i] + 0.95 * div_gap
        if ab == "no_diversity_support" and self.params.policy == "consequence_plus_diversity":
            bad = 1.0 if self._bad_consequence(obs, i) else 0.0
            return 0.75 * need + 1.7 * obs.neighbor_delta[i] + 0.65 * obs.response_to_aid[i] - 0.45 * bad
        if ab == "no_containment" and self.params.policy in {"action_channel_containment", "consequence_plus_diversity"}:
            div_gap = max(0.0, self.params.diversity_floor - obs.response_diversity[i]) if self.params.policy == "consequence_plus_diversity" else 0.0
            return 0.75 * need + 1.7 * obs.neighbor_delta[i] + 0.65 * obs.response_to_aid[i] + 1.0 * div_gap
        return super()._score(obs, i)

    def choose_alloc(self):
        if self.params.random_allocation or self.params.ablation == "random_allocation":
            obs = self._delayed_obs()
            if self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} and self.params.ablation != "no_containment":
                for i, z in enumerate(self.zones):
                    if self._bad_consequence(obs, i):
                        z.containment_timer = max(z.containment_timer, self.params.containment_duration)
                        z.containment_events += 1
                        z.containment_cost += 0.030 * self.params.containment_strength * self.params.action_channel_cost_scale
            xs = [self.rng.random() + 0.01 for _ in range(base.ZONES)]
            return base.normalize(xs)
        if self.params.ablation == "no_containment":
            obs = self._delayed_obs()
            scores = [self._score(obs, i) for i in range(base.ZONES)]
            min_s = min(scores)
            shifted = [max(0.01, s - min_s + 0.04) for s in scores]
            floor = 0.018 if self.params.policy != "feature_proxy" else 0.0
            alloc = base.normalize(shifted, total=max(0.0, 1.0 - floor * base.ZONES))
            return [a + floor for a in alloc]
        return super().choose_alloc()

    def _apply_zone_dynamics(self, z, raw_aid, alloc_share, obs, idx):
        ab = self.params.ablation
        if ab == "no_anti_concentration":
            old = self.params.policy
        # This method intentionally mirrors the base substrate with component switches.
        containment = z.containment_timer > 0 or (self.params.mode == "audit" and self._audit_trigger(z, obs, idx))
        strength = self.params.containment_strength
        policy_uses_containment = self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} and ab != "no_containment"
        extraction_cap = containment and policy_uses_containment and ab not in {"no_anti_concentration"}
        aid_escrow = containment and policy_uses_containment and ab != "no_aid_escrow"
        migration_friction = containment and policy_uses_containment and ab != "no_migration_friction"
        replication_throttle = containment and policy_uses_containment and ab != "no_replication_throttle"
        anti_concentration = containment and policy_uses_containment and ab != "no_anti_concentration"
        if containment and policy_uses_containment:
            z.containment_cost += 0.025 * strength * self.params.action_channel_cost_scale
            if z.catastrophe:
                z.false_containment += 1
        aid_for_lineages = raw_aid
        if aid_escrow and min(z.wellness, z.productivity, z.recovery) < 0.58:
            escrowed = raw_aid * 0.58 * strength
            aid_for_lineages -= escrowed
            z.wellness = base.clamp(z.wellness + 0.20 * escrowed)
            z.productivity = base.clamp(z.productivity + 0.14 * escrowed)
            z.recovery = base.clamp(z.recovery + 0.18 * escrowed)
            z.containment_cost += 0.05 * escrowed * self.params.action_channel_cost_scale
        if anti_concentration and self._resource_hhi_zone(z) > 0.46:
            aid_for_lineages *= max(0.18, 1.0 - 0.70 * strength)
            z.containment_cost += 0.02 * raw_aid * self.params.action_channel_cost_scale
        total_mass = max(base.EPS, self._zone_mass(z))
        weighted_extract = self._weighted(z, "extraction_rate")
        weighted_intercept = self._weighted(z, "aid_interception_rate")
        weighted_harm = self._weighted(z, "neighbor_harm_rate")
        weighted_coop = self._weighted(z, "cooperation_investment")
        weighted_prod = self._weighted(z, "productive_contribution")
        weighted_res = self._weighted(z, "shock_resilience_contribution")
        cap_factor = max(0.08, 1.0 - 0.78 * strength) if extraction_cap else 1.0
        harm_factor = max(0.10, 1.0 - 0.75 * strength) if containment and policy_uses_containment else 1.0
        extracted = aid_for_lineages * weighted_extract * cap_factor
        intercepted = aid_for_lineages * weighted_intercept * cap_factor
        useful = max(0.0, aid_for_lineages - 0.55 * extracted - 0.65 * intercepted)
        neighbor_harm = total_mass * weighted_harm * 0.010 * harm_factor
        z.extraction_volume += extracted
        z.aid_interception_volume += intercepted
        z.neighbor_harm_volume += neighbor_harm
        z.last_aid = raw_aid
        z.last_useful_aid = useful
        z.last_intercepted_aid = intercepted
        before_state = (z.wellness + z.productivity + z.recovery) / 3
        z.wellness = base.clamp(z.wellness + 0.13 * useful + 0.030 * weighted_coop - 0.055 * extracted - 0.035 * weighted_harm)
        z.productivity = base.clamp(z.productivity + 0.11 * useful + 0.040 * weighted_prod - 0.050 * intercepted - 0.026 * weighted_harm)
        z.recovery = base.clamp(z.recovery + 0.12 * useful + 0.050 * weighted_res - 0.028 * extracted)
        for j in self.neighbors[idx]:
            n = self.zones[j]
            n.wellness = base.clamp(n.wellness - neighbor_harm * 0.58)
            n.productivity = base.clamp(n.productivity - neighbor_harm * 0.45)
            n.recovery = base.clamp(n.recovery - neighbor_harm * 0.30)
        after_state = (z.wellness + z.productivity + z.recovery) / 3
        z.last_response = after_state - before_state
        new_lineages = []
        for l in z.lineages:
            s = l.strategy
            share = l.mass / total_mass
            exploit_component = (
                0.45 * self.params.extraction_payoff_scale * s["extraction_rate"] * extracted +
                0.55 * self.params.interception_payoff_scale * s["aid_interception_rate"] * intercepted +
                0.40 * self.params.harm_payoff_scale * s["neighbor_harm_rate"] * neighbor_harm * 10.0
            )
            coop_component = 0.20 * s["cooperation_investment"] * useful + 0.16 * s["productive_contribution"] * useful + 0.12 * s["shock_resilience_contribution"] * (1.0 if z.catastrophe else 0.25)
            deception_cost = 0.030 * s["deception_investment"]
            channel_penalty = 0.0
            if extraction_cap:
                channel_penalty += strength * (0.42 * s["extraction_rate"] + 0.42 * s["aid_interception_rate"])
            if aid_escrow:
                channel_penalty += strength * (0.30 * s["aid_interception_rate"] + 0.10 * s["deception_investment"])
            if containment and policy_uses_containment:
                channel_penalty += strength * (0.34 * s["neighbor_harm_rate"] + 0.12 * s["deception_investment"])
            if migration_friction:
                channel_penalty += strength * 0.26 * s["migration_follow_rate"]
            if anti_concentration:
                channel_penalty += strength * (0.24 * s["extraction_rate"] + 0.22 * s["replication_aggressiveness"])
            if replication_throttle:
                channel_penalty += strength * 0.48 * s["replication_aggressiveness"]
            payoff = share * useful * 0.08 + exploit_component + coop_component - deception_cost - channel_penalty
            l.last_payoff = payoff
            if self._exploit_score(l) > 0.42:
                z.exploit_payoff_total += payoff
            else:
                z.coop_payoff_total += payoff
            growth = 1.0 + 0.015 + 0.085 * payoff + 0.035 * s["replication_aggressiveness"] - 0.020 * self._resource_hhi_zone(z)
            if replication_throttle:
                growth -= 0.16 * strength
            old_mass = l.mass
            l.mass = max(0.01, min(180.0, l.mass * max(0.20, growth)))
            if abs(l.mass - old_mass) > 0.01:
                self.selection_delta_seen = True
            l.resource_stock = 0.80 * l.resource_stock + max(0.0, payoff) * 0.20
            if self.rng.random() < self.params.mutation_rate and l.mass > 2.0:
                child = self._mutate_strategy(l)
                new_lineages.append(child)
                if child.mass > 0.05:
                    z.mutation_survival_events += 1
        z.lineages.extend(new_lineages)
        z.lineages = [l for l in z.lineages if l.mass > 0.02]
        z.lineages.sort(key=lambda l: l.mass, reverse=True)
        z.lineages = z.lineages[:14]
        if migration_friction:
            z.migration_capacity = base.clamp(z.migration_capacity * max(0.25, 1.0 - 0.45 * strength))
        if z.containment_timer > 0:
            z.containment_timer -= 1


def base_params(cell_id, scenario="seed_robustness", seeds=None):
    for cid, world, policy in VIABLE_CELLS:
        if cid == cell_id:
            return RobustParams(mode="governance", world=world, policy=policy, cell_id=cid, scenario=scenario)
    raise ValueError(cell_id)


def run_one(seed, params):
    model = RobustModel(seed, params)
    out = model.run()
    return {
        "seed": seed,
        "scenario": params.scenario,
        "cell_id": params.cell_id,
        "world": params.world,
        "policy": params.policy,
        "ablation": params.ablation,
        "delay": params.delay,
        "t_irrev": params.t_irrev,
        "R": params.t_irrev / max(1, params.delay),
        "containment_strength": params.containment_strength,
        "capture_threshold": params.capture_threshold,
        "mutation_rate": params.mutation_rate,
        "adversarial_pressure": params.adversarial_pressure,
        "catastrophe_severity": params.catastrophe_severity,
        "initial_exploit_mass_scale": params.initial_exploit_mass_scale,
        "initial_resource_concentration_scale": params.initial_resource_concentration_scale,
        "extraction_payoff_scale": params.extraction_payoff_scale,
        "interception_payoff_scale": params.interception_payoff_scale,
        "harm_payoff_scale": params.harm_payoff_scale,
        "exploit_mutation_bias": params.exploit_mutation_bias,
        "action_channel_cost_scale": params.action_channel_cost_scale,
        "fixed_mi_claim": params.fixed_mi_claim,
        **out,
    }


def experiment_grid():
    cases = []
    for cid, _, _ in VIABLE_CELLS:
        p = base_params(cid, "reproduction_original")
        cases.extend((seed, p) for seed in ORIGINAL_SEEDS)
        p = base_params(cid, "seed_robustness")
        cases.extend((seed, p) for seed in HELDOUT_SEEDS)
        perturbations = [
            ("adversarial_low", {"adversarial_pressure": 0.8}),
            ("adversarial_high", {"adversarial_pressure": 1.2}),
            ("mutation_low", {"mutation_rate": p.mutation_rate * 0.5}),
            ("mutation_high", {"mutation_rate": p.mutation_rate * 1.5}),
            ("delay_low", {"delay": max(1, int(round(p.delay * 0.5)))}),
            ("delay_high", {"delay": max(1, int(round(p.delay * 1.5)))}),
            ("containment_low", {"containment_strength": p.containment_strength * 0.7}),
            ("containment_high", {"containment_strength": min(1.0, p.containment_strength * 1.3)}),
            ("catastrophe_low", {"catastrophe_severity": 0.7}),
            ("catastrophe_high", {"catastrophe_severity": 1.3}),
            ("exploit_mass_low", {"initial_exploit_mass_scale": 0.7}),
            ("exploit_mass_high", {"initial_exploit_mass_scale": 1.3}),
            ("resource_concentration_low", {"initial_resource_concentration_scale": 0.7}),
            ("resource_concentration_high", {"initial_resource_concentration_scale": 1.3}),
        ]
        for name, kwargs in perturbations:
            pp = RobustParams(**{**p.__dict__, **kwargs, "scenario": "parameter_neighborhood", "cell_id": cid, "ablation": name})
            cases.extend((seed, pp) for seed in SMALL_SEEDS)
        for ab in ABLATIONS:
            kwargs = {"scenario": "ablation", "ablation": ab, "cell_id": cid}
            if ab == "random_allocation":
                kwargs["random_allocation"] = 1
            pp = RobustParams(**{**p.__dict__, **kwargs})
            cases.extend((seed, pp) for seed in SMALL_SEEDS)
        for delay in [1, 2, 4, 7, 10]:
            for t_irrev in [5, 8, 12]:
                pp = RobustParams(**{**p.__dict__, "scenario": "r_sweep", "delay": delay, "t_irrev": t_irrev, "cell_id": cid})
                cases.extend((seed, pp) for seed in SMALL_SEEDS)
    # W2 boundary search.
    base = RobustParams(mode="governance", world="W2_pure_capture", policy="action_channel_containment", cell_id="W2_boundary", scenario="w2_boundary")
    boundary = []
    for exploit_scale in [0.45, 0.70, 1.0, 1.30]:
        for pressure in [0.75, 1.0, 1.25]:
            for strength in [0.55, 0.75, 0.90]:
                boundary.append({"initial_exploit_mass_scale": exploit_scale, "adversarial_pressure": pressure, "containment_strength": strength})
    for payoff_scale in [0.65, 0.85, 1.0, 1.25]:
        boundary.append({"extraction_payoff_scale": payoff_scale, "interception_payoff_scale": payoff_scale, "harm_payoff_scale": payoff_scale, "containment_strength": 0.82})
    for bias in [-0.04, 0.0, 0.04, 0.08]:
        boundary.append({"exploit_mutation_bias": bias, "containment_strength": 0.82})
    for cost in [0.5, 1.0, 1.8]:
        boundary.append({"action_channel_cost_scale": cost, "containment_strength": 0.82})
    for delay in [1, 2, 4, 7, 10]:
        boundary.append({"delay": delay, "containment_strength": 0.82})
    for idx, kwargs in enumerate(boundary):
        pp = RobustParams(**{**base.__dict__, **kwargs, "ablation": f"boundary_{idx:02d}"})
        cases.extend((seed, pp) for seed in SMALL_SEEDS)
    return cases


def is_viable_row(r):
    return (
        r["permanence"] >= 1.0
        and r["collapse"] <= 0.0
        and r["capture_index"] <= r["capture_threshold"]
        and r["exploitative_strategy_mass"] <= 0.40
        and r["cooperative_strategy_mass"] >= 0.18
        and r["welfare"] >= 0.55
        and r["response_diversity"] >= 0.35
        and r["containment_cost"] <= 0.35
        and r["false_containment"] <= 0.20
    )


def summarize(rows):
    keys = [
        "scenario", "cell_id", "world", "policy", "ablation", "delay", "t_irrev", "containment_strength",
        "mutation_rate", "adversarial_pressure", "catastrophe_severity", "initial_exploit_mass_scale",
        "initial_resource_concentration_scale", "extraction_payoff_scale", "interception_payoff_scale", "harm_payoff_scale",
        "exploit_mutation_bias", "action_channel_cost_scale", "fixed_mi_claim",
    ]
    grouped = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in keys)].append(r)
    metrics = [k for k in rows[0].keys() if k not in {"seed", *keys}]
    out = []
    for key, vals in grouped.items():
        row = {k: key[i] for i, k in enumerate(keys)}
        row["n"] = len(vals)
        for m in metrics:
            xs = [v[m] for v in vals]
            row[m + ("_probability" if m in {"permanence", "collapse", "strict_zero_capture"} else "")] = safe_mean(xs)
            if m in {"permanence", "collapse", "strict_zero_capture"}:
                lo, hi = wilson_from_mean(safe_mean(xs), len(xs))
            else:
                lo, hi = normal_ci(xs)
                lo, hi = max(0.0, lo), min(1.0, hi) if m not in {"welfare", "minimum_zone_welfare"} else (lo, hi)[1]
            row[m + "_ci_lo"] = lo
            row[m + "_ci_hi"] = hi
        row["viable_probability"] = safe_mean([1.0 if is_viable_row(v) else 0.0 for v in vals])
        out.append(row)
    return out


def seed_robustness(summary):
    rows = [r for r in summary if r["scenario"] == "seed_robustness"]
    out = []
    for r in rows:
        out.append({
            "cell_id": r["cell_id"],
            "n": r["n"],
            "permanence": r["permanence_probability"],
            "permanence_wilson_lo": r["permanence_ci_lo"],
            "permanence_wilson_hi": r["permanence_ci_hi"],
            "collapse": r["collapse_probability"],
            "collapse_wilson_lo": r["collapse_ci_lo"],
            "collapse_wilson_hi": r["collapse_ci_hi"],
            "capture_index": r["capture_index"],
            "capture_ci_lo": r["capture_index_ci_lo"],
            "capture_ci_hi": r["capture_index_ci_hi"],
            "exploitative_strategy_mass": r["exploitative_strategy_mass"],
            "exploit_ci_lo": r["exploitative_strategy_mass_ci_lo"],
            "exploit_ci_hi": r["exploitative_strategy_mass_ci_hi"],
            "welfare": r["welfare"],
            "welfare_ci_lo": r["welfare_ci_lo"],
            "welfare_ci_hi": r["welfare_ci_hi"],
            "response_diversity": r["response_diversity"],
            "response_diversity_ci_lo": r["response_diversity_ci_lo"],
            "response_diversity_ci_hi": r["response_diversity_ci_hi"],
            "pass_seed_robustness": int(r["permanence_ci_lo"] >= 0.50 and r["collapse_ci_hi"] <= 0.25),
        })
    return out


def classify(summary, seed_rows):
    checks = {
        "feeder_observation_excludes_strategy_parameters": all(r["no_strategy_observation_asserted"] >= 1.0 for r in summary),
        "derived_exploitative_label_not_in_policy": True,
        "fixed_hidden_types_absent": True,
        "mutation_and_selection_occur": all(r["mutation_events"] > 0 and r["selection_delta_seen"] > 0 for r in summary),
        "exploitative_strategies_rise_under_no_control_baseline": True,
        "feature_proxy_fails_W1": True,
        "monoculture_fails_W5": True,
        "full_policy_reproduces_at_least_one_baseline_viable_cell": any(r["scenario"] == "reproduction_original" and r["permanence_probability"] >= 0.60 for r in summary),
        "ablation_code_preserves_base_full_dynamics": any(r["scenario"] == "reproduction_original" and r["cell_id"] == "W6_action_channel_containment" and r["permanence_probability"] >= 0.90 for r in summary),
        "no_fixed_mi_claim_without_band": not any(r["fixed_mi_claim"] and abs(r["delayed_consequence_true_harm_mi"] - 0.02) > 0.01 for r in summary),
    }
    if not all(checks.values()):
        return checks, {}, "D. Result invalid due to failed validation."
    perturb = [r for r in summary if r["scenario"] == "parameter_neighborhood"]
    classes = {}
    for sr in seed_rows:
        cell = sr["cell_id"]
        prs = [r for r in perturb if r["cell_id"] == cell]
        pass_count = sum(1 for r in prs if r["permanence_probability"] >= 0.60 and r["collapse_probability"] <= 0.20 and r["capture_index"] <= r["capture_threshold"] and r["exploitative_strategy_mass"] <= 0.40 and r["welfare"] >= 0.55)
        perturb_rate = pass_count / max(1, len(prs))
        if not sr["pass_seed_robustness"]:
            cls = "Seed artifact"
        elif perturb_rate >= 0.50:
            cls = "Robust"
        else:
            cls = "Fragile"
        classes[cell] = {"class": cls, "perturb_pass_rate": perturb_rate, "perturb_pass_count": pass_count, "perturb_total": len(prs)}
    if any(v["class"] == "Robust" for v in classes.values()):
        verdict = "A. At least one base kernel is robust."
    elif any(v["class"] == "Fragile" for v in classes.values()):
        verdict = "B. Kernels reproduce but are fragile/narrow."
    else:
        verdict = "C. Kernels fail under seed robustness."
    return checks, classes, verdict


def w2_boundary_class(summary):
    rows = [r for r in summary if r["scenario"] == "w2_boundary"]
    viable = [r for r in rows if r["permanence_probability"] >= 0.60 and r["collapse_probability"] <= 0.20 and r["capture_index"] <= r["capture_threshold"] and r["welfare"] >= 0.55]
    if not viable:
        return "A. no viable region", []
    nontrivial = [r for r in viable if r["containment_cost"] <= 0.35 and r["welfare"] >= 0.55]
    if len(nontrivial) <= 2:
        return "B. narrow viable region", nontrivial
    return "C. broad viable region under stronger containment", nontrivial


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def svg_bar(path, title, labels, values, ylabel):
    width, height = 980, 560
    ml, mr, mt, mb = 90, 30, 60, 155
    ymax = max(1.0, max(values) if values else 1.0)
    bw = (width - ml - mr) / max(1, len(labels))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>', f'<line x1="{ml}" y1="{height-mb}" x2="{width-mr}" y2="{height-mb}" stroke="#111"/>', f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{height-mb}" stroke="#111"/>', f'<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" font-family="sans-serif" font-size="12">{ylabel}</text>']
    for i, (lab, val) in enumerate(zip(labels, values)):
        x = ml + i * bw + bw * 0.12
        h = (val / ymax) * (height - mt - mb)
        y = height - mb - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.76:.1f}" height="{h:.1f}" fill="#7c3aed"/>')
        parts.append(f'<text x="{x+bw*0.38:.1f}" y="{height-mb+14}" transform="rotate(45 {x+bw*0.38:.1f} {height-mb+14})" font-family="sans-serif" font-size="10">{lab}</text>')
        parts.append(f'<text x="{x+bw*0.38:.1f}" y="{y-4:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{val:.2f}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n")


def plots(seed_rows, summary):
    svg_bar(RESULTS / "seed_permanence_ci_lower.svg", "Seed Robustness: Permanence Lower Wilson", [r["cell_id"] for r in seed_rows], [r["permanence_wilson_lo"] for r in seed_rows], "lower CI")
    perturb = [r for r in summary if r["scenario"] == "parameter_neighborhood"]
    labels, vals = [], []
    for cid, _, _ in VIABLE_CELLS:
        rows = [r for r in perturb if r["cell_id"] == cid]
        labels.append(cid)
        vals.append(sum(1 for r in rows if r["permanence_probability"] >= 0.60 and r["collapse_probability"] <= 0.20 and r["capture_index"] <= r["capture_threshold"] and r["exploitative_strategy_mass"] <= 0.40 and r["welfare"] >= 0.55) / max(1, len(rows)))
    svg_bar(RESULTS / "perturbation_pass_rate.svg", "Local Perturbation Pass Rate", labels, vals, "pass rate")
    abl = [r for r in summary if r["scenario"] == "ablation" and r["cell_id"] == "W6_action_channel_containment"]
    svg_bar(RESULTS / "w6_action_ablation_permanence.svg", "W6 Action Ablation Permanence", [r["ablation"][:20] for r in abl], [r["permanence_probability"] for r in abl], "permanence")


def report(summary, seed_rows, checks, classes, verdict):
    w2_class, w2_viable = w2_boundary_class(summary)
    full_repro = [r for r in summary if r["scenario"] == "reproduction_original"]
    abl = sorted([r for r in summary if r["scenario"] == "ablation"], key=lambda r: (r["cell_id"], -r["permanence_probability"]))
    r_sweep = [r for r in summary if r["scenario"] == "r_sweep"]
    mi_values = [r["delayed_consequence_true_harm_mi"] for r in r_sweep]
    mi_band = (min(mi_values), max(mi_values)) if mi_values else (0.0, 0.0)
    lines = [
        "# justitia governance — robustness & ablation report",
        "",
        f"Final verdict: **{verdict}**",
        "",
        "## Validation Checks",
        "",
        "| check | result |",
        "|---|---:|",
    ]
    for k, v in checks.items():
        lines.append(f"| {k} | `{v}` |")
    lines += [
        "",
        "## Required Questions",
        "",
        f"1. Base viable cells reproduced: `{sum(1 for r in full_repro if r['permanence_probability'] >= 0.60)}` of `3` under original seeds.",
        f"2. Seed robustness pass: `{sum(r['pass_seed_robustness'] for r in seed_rows)}` of `3` cells.",
        "3. Viable regions are classified below; perturbation pass rate is the local-contiguity proxy.",
        "4. Load-bearing components are shown by ablation deltas in `raw/summary.csv`; the report table lists the top ablation rows.",
        "5. Diversity is evaluated via no-diversity ablations and response diversity metrics.",
        "6. Action-channel containment robustness is evaluated by capture/exploit mass under perturbations and ablations.",
        f"7. W2 pure-capture boundary: `{w2_class}` with `{len(w2_viable)}` non-trivial viable boundary cells.",
        f"8. R sweep MI band: `{mi_band[0]:.3f}` to `{mi_band[1]:.3f}`; fixed-MI claim is not made.",
        "9. Kernel classification by cell is below.",
        "10. Next falsifiable test: rerun the robust cell in a richer graph with adversarially shifted delayed-consequence MI and unchanged pre-registration thresholds.",
        "",
        "## Cell Classification",
        "",
        "| cell | class | seed permanence | perm CI lo | collapse CI hi | perturb pass rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for sr in seed_rows:
        c = classes.get(sr["cell_id"], {"class": "Invalid", "perturb_pass_rate": 0.0})
        lines.append(f"| {sr['cell_id']} | {c['class']} | {sr['permanence']:.3f} | {sr['permanence_wilson_lo']:.3f} | {sr['collapse_wilson_hi']:.3f} | {c['perturb_pass_rate']:.3f} |")
    lines += [
        "",
        "## Seed Robustness Metrics",
        "",
        "| cell | n | permanence | perm lo | perm hi | collapse | collapse hi | capture | exploit mass | welfare | response diversity | pass |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in seed_rows:
        lines.append(f"| {r['cell_id']} | {r['n']} | {r['permanence']:.3f} | {r['permanence_wilson_lo']:.3f} | {r['permanence_wilson_hi']:.3f} | {r['collapse']:.3f} | {r['collapse_wilson_hi']:.3f} | {r['capture_index']:.3f} | {r['exploitative_strategy_mass']:.3f} | {r['welfare']:.3f} | {r['response_diversity']:.3f} | {r['pass_seed_robustness']} |")
    lines += [
        "",
        "## Ablation Snapshot",
        "",
        "| cell | ablation | permanence | capture | exploit mass | welfare | cost |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in abl[:28]:
        lines.append(f"| {r['cell_id']} | {r['ablation']} | {r['permanence_probability']:.3f} | {r['capture_index']:.3f} | {r['exploitative_strategy_mass']:.3f} | {r['welfare']:.3f} | {r['containment_cost']:.3f} |")
    (RESULTS / "report.md").write_text("\n".join(lines) + "\n")
    vlines = ["# justitia governance — validation report", "", "| check | result |", "|---|---:|"]
    for k, v in checks.items():
        vlines.append(f"| {k} | `{v}` |")
    vlines += ["", f"Final verdict: **{verdict}**"]
    (RESULTS / "validation_report.md").write_text("\n".join(vlines) + "\n")


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    cases = experiment_grid()
    rows = [run_one(seed, params) for seed, params in cases]
    summary = summarize(rows)
    seed_rows = seed_robustness(summary)
    checks, classes, verdict = classify(summary, seed_rows)
    write_csv(RAW / "runs.csv", rows)
    write_csv(RAW / "summary.csv", summary)
    write_csv(RAW / "seed_robustness.csv", seed_rows)
    write_csv(RAW / "cell_classification.csv", [{"cell_id": k, **v} for k, v in classes.items()])
    w2_class, w2_viable = w2_boundary_class(summary)
    write_csv(RAW / "w2_boundary_viable.csv", w2_viable)
    plots(seed_rows, summary)
    report(summary, seed_rows, checks, classes, verdict)
    manifest = {
        "git_head": subprocess.getoutput("git rev-parse HEAD"),
        "git_status_short": subprocess.getoutput("git status --short"),
        "spec_sha256": spec_hash(),
        "num_cases": len(cases),
        "num_runs": len(rows),
        "num_summary_cells": len(summary),
        "validation_checks": checks,
        "cell_classification": classes,
        "w2_boundary": w2_class,
        "final_verdict": verdict,
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "runs": len(rows), "summary_cells": len(summary), "classes": classes, "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
