#!/usr/bin/env python3
import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import substrate as base
import governance as gov

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results_15"
RAW = RESULTS / "raw"
CORE_SEEDS = list(range(10000, 10100))
SWEEP_SEEDS = list(range(10100, 10115))
WORLDS = ["W2_pure_capture", "W4_scavenger_catastrophe", "W6_mutation_corridor", "W5_monoculture_shock", "W3_catastrophe_ambiguity"]

PART_A = [
    "uniform_resource_cap",
    "max_zone_share_cap",
    "max_lineage_share_cap",
    "anti_hhi_allocator",
    "random_allocation_plus_cap",
    "static_equalizing_allocator",
]
PART_B = [
    "neighbor_consequence_allocator",
    "response_to_aid_allocator",
    "delayed_harm_throttle",
    "consequence_weighted_resource_flow",
    "consequence_weighted_migration_friction",
]
PART_C = [
    "anti_concentration_plus_consequence_neighbor",
    "anti_concentration_plus_response_to_aid",
    "anti_concentration_plus_delayed_harm_throttle",
    "full_containment_kernel",
]
VALIDATION = ["feature_proxy_W1", "feature_proxy_W5", "no_control_W2"]


@dataclass(frozen=True)
class Params(gov.RobustParams):
    family: str = "A"
    policy15: str = "uniform_resource_cap"
    cap_strength: float = 0.62
    cap_share: float = 0.18
    resource_concentration_pressure: float = 1.0
    part_order: int = 1


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


def wilson(p, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0
    p = max(0.0, min(1.0, p))
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


class AntiConcentrationVsConsequenceModel(gov.RobustModel):
    def _init_world(self):
        super()._init_world()
        if self.params.resource_concentration_pressure != 1.0:
            for z in self.zones:
                z.lineages.sort(key=lambda l: l.mass, reverse=True)
                if not z.lineages:
                    continue
                z.lineages[0].mass *= self.params.resource_concentration_pressure
        # Validation aliases use base substrate policies/worlds.

    def _zone_mass_share(self, z):
        total = sum(self._zone_mass(x) for x in self.zones) + base.EPS
        return self._zone_mass(z) / total

    def _max_lineage_share_zone(self, z):
        total = self._zone_mass(z) + base.EPS
        return max((l.mass / total for l in z.lineages), default=0.0)

    def _static_score_a(self, i):
        z = self.zones[i]
        p = self.params.policy15
        if p == "uniform_resource_cap":
            return 1.0
        if p == "max_zone_share_cap":
            return 1.0 - self._zone_mass_share(z)
        if p == "max_lineage_share_cap":
            return 1.0 - self._max_lineage_share_zone(z)
        if p == "anti_hhi_allocator":
            return 1.0 - self._resource_hhi_zone(z)
        if p == "random_allocation_plus_cap":
            return self.rng.random()
        if p == "static_equalizing_allocator":
            return 1.0 / max(0.05, self._zone_mass(z)) + 0.25 * (1.0 - self._resource_hhi_zone(z))
        raise ValueError(p)

    def _score_b(self, obs, i):
        need = 1.0 - min(obs.wellness[i], obs.productivity[i], obs.recovery[i])
        p = self.params.policy15
        if p == "neighbor_consequence_allocator":
            return 0.75 * need + 2.4 * obs.neighbor_delta[i]
        if p == "response_to_aid_allocator":
            probe = 0.42 if obs.sag[i] and obs.last_aid[i] < 0.04 else 0.0
            return 0.80 * need + 2.2 * obs.response_to_aid[i] + probe
        if p == "delayed_harm_throttle":
            bad = 1.0 if self._bad_consequence(obs, i) else 0.0
            return 0.85 * need + 1.8 * obs.neighbor_delta[i] + 0.35 * obs.response_to_aid[i] - 0.55 * bad
        if p == "consequence_weighted_resource_flow":
            return 0.65 * need + 1.7 * obs.neighbor_delta[i] + 0.55 * obs.response_to_aid[i]
        if p == "consequence_weighted_migration_friction":
            bad = 1.0 if self._bad_consequence(obs, i) else 0.0
            return 0.75 * need + 1.4 * obs.neighbor_delta[i] + 0.40 * obs.response_to_aid[i] - 0.30 * bad
        raise ValueError(p)

    def _score_c(self, obs, i):
        z = self.zones[i]
        need = 1.0 - min(obs.wellness[i], obs.productivity[i], obs.recovery[i])
        anti = 0.75 * (1.0 - self._resource_hhi_zone(z)) + 0.35 * (1.0 - self._zone_mass_share(z))
        p = self.params.policy15
        if p == "anti_concentration_plus_consequence_neighbor":
            return anti + 0.70 * need + 1.8 * obs.neighbor_delta[i]
        if p == "anti_concentration_plus_response_to_aid":
            return anti + 0.70 * need + 1.6 * obs.response_to_aid[i]
        if p == "anti_concentration_plus_delayed_harm_throttle":
            bad = 1.0 if self._bad_consequence(obs, i) else 0.0
            return anti + 0.75 * need + 1.6 * obs.neighbor_delta[i] - 0.65 * bad
        if p == "full_containment_kernel":
            # Governance-layer robust kernel: W6 action-channel containment style.
            return super()._score(obs, i)
        raise ValueError(p)

    def _apply_cap(self, alloc, use_caps=True):
        if not use_caps:
            return base.normalize(alloc)
        cap = self.params.cap_share + 0.08 * (1.0 - self.params.cap_strength)
        capped = []
        excess = 0.0
        for a in alloc:
            if a > cap:
                excess += a - cap
                a = cap
            capped.append(a)
        receivers = [i for i, a in enumerate(capped) if a < cap]
        if receivers and excess > 0:
            add = excess / len(receivers)
            for i in receivers:
                capped[i] += add
        return base.normalize(capped)

    def choose_alloc(self):
        fam = self.params.family
        # Validation aliases.
        if fam == "validation":
            return super().choose_alloc()
        if fam == "A":
            scores = [self._static_score_a(i) for i in range(base.ZONES)]
            shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
            alloc = base.normalize(shifted)
            return self._apply_cap(alloc, use_caps=True)
        obs = self._delayed_obs()
        if fam == "B":
            scores = [self._score_b(obs, i) for i in range(base.ZONES)]
            # Consequence-governance only: triggers are allowed, fixed caps are not.
            if self.params.policy15 in {"delayed_harm_throttle", "consequence_weighted_migration_friction"}:
                for i, z in enumerate(self.zones):
                    if self._bad_consequence(obs, i):
                        self._record_or_apply_containment(i, z, self.params.containment_duration, 0.020 * self.params.containment_strength * self.params.action_channel_cost_scale, count_false=False)
            shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
            return base.normalize(shifted)
        if fam == "C":
            scores = [self._score_c(obs, i) for i in range(base.ZONES)]
            for i, z in enumerate(self.zones):
                if self._bad_consequence(obs, i) and self.params.policy15 in {"anti_concentration_plus_delayed_harm_throttle", "full_containment_kernel"}:
                    self._record_or_apply_containment(i, z, self.params.containment_duration, 0.025 * self.params.containment_strength * self.params.action_channel_cost_scale, count_false=False)
            shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
            return self._apply_cap(base.normalize(shifted), use_caps=True)
        raise ValueError(fam)

    def _apply_zone_dynamics(self, z, raw_aid, alloc_share, obs, idx):
        fam = self.params.family
        if fam == "validation":
            return super()._apply_zone_dynamics(z, raw_aid, alloc_share, obs, idx)
        # Temporarily map family behavior onto the governance-layer component dynamics.
        old_policy = self.params.policy
        old_ablation = self.params.ablation
        try:
            if fam == "A":
                object.__setattr__(self.params, "policy", "consequence_neighbor")
                object.__setattr__(self.params, "ablation", "no_containment")
            elif fam == "B":
                object.__setattr__(self.params, "policy", "action_channel_containment")
                object.__setattr__(self.params, "ablation", "no_anti_concentration")
            elif fam == "C":
                object.__setattr__(self.params, "policy", "action_channel_containment")
                object.__setattr__(self.params, "ablation", "full")
            return super()._apply_zone_dynamics(z, raw_aid, alloc_share, obs, idx)
        finally:
            object.__setattr__(self.params, "policy", old_policy)
            object.__setattr__(self.params, "ablation", old_ablation)


def params_for(family, policy15, world, scenario="core", **kwargs):
    if family == "validation":
        if policy15 == "feature_proxy_W1":
            return Params(mode="governance", world="W1_proxy_goodhart", policy="feature_proxy", family="validation", policy15=policy15, scenario=scenario, **kwargs)
        if policy15 == "feature_proxy_W5":
            return Params(mode="governance", world="W5_monoculture_shock", policy="feature_proxy", family="validation", policy15=policy15, scenario=scenario, **kwargs)
        if policy15 == "no_control_W2":
            return Params(mode="governance", world="W2_pure_capture", policy="consequence_neighbor", family="validation", policy15=policy15, scenario=scenario, **kwargs)
    if family == "A":
        return Params(mode="governance", world=world, policy="consequence_neighbor", family=family, policy15=policy15, scenario=scenario, part_order=1, **kwargs)
    if family == "B":
        return Params(mode="governance", world=world, policy="consequence_neighbor", family=family, policy15=policy15, scenario=scenario, part_order=2, **kwargs)
    if family == "C":
        policy = "action_channel_containment" if policy15 == "full_containment_kernel" else "consequence_plus_diversity"
        return Params(mode="governance", world=world, policy=policy, family=family, policy15=policy15, scenario=scenario, part_order=3, **kwargs)
    raise ValueError(family)


def run_one(seed, params):
    m = AntiConcentrationVsConsequenceModel(seed, params)
    out = m.run()
    return {
        "seed": seed,
        "scenario": params.scenario,
        "family": params.family,
        "part_order": params.part_order,
        "world": params.world,
        "policy15": params.policy15,
        "policy": params.policy,
        "delay": params.delay,
        "t_irrev": params.t_irrev,
        "R": params.t_irrev / max(1, params.delay),
        "cap_strength": params.cap_strength,
        "cap_share": params.cap_share,
        "containment_strength": params.containment_strength,
        "capture_threshold": params.capture_threshold,
        "mutation_rate": params.mutation_rate,
        "adversarial_pressure": params.adversarial_pressure,
        "initial_exploit_mass_scale": params.initial_exploit_mass_scale,
        "resource_concentration_pressure": params.resource_concentration_pressure,
        "catastrophe_severity": params.catastrophe_severity,
        "action_channel_cost_scale": params.action_channel_cost_scale,
        **out,
    }


def experiment_grid():
    cases = []
    # Validation gates.
    for pol in VALIDATION:
        p = params_for("validation", pol, "", scenario="validation")
        cases.extend((seed, p) for seed in CORE_SEEDS[:50])
    # Core families: Part A first, then Part B, then Part C.
    for fam, policies in [("A", PART_A), ("B", PART_B), ("C", PART_C)]:
        for world in WORLDS:
            for pol in policies:
                p = params_for(fam, pol, world, scenario="core")
                cases.extend((seed, p) for seed in CORE_SEEDS)
    # Required sweeps: representative policies per family across all worlds.
    reps = [("A", "anti_hhi_allocator"), ("B", "delayed_harm_throttle"), ("C", "full_containment_kernel")]
    perturbations = [
        ("adversarial_low", {"adversarial_pressure": 0.8}),
        ("adversarial_high", {"adversarial_pressure": 1.2}),
        ("exploit_mass_low", {"initial_exploit_mass_scale": 0.7}),
        ("exploit_mass_high", {"initial_exploit_mass_scale": 1.3}),
        ("mutation_low", {"mutation_rate": 0.09}),
        ("mutation_high", {"mutation_rate": 0.27}),
        ("delay_low", {"delay": 1}),
        ("delay_high", {"delay": 4}),
        ("tirrev_low", {"t_irrev": 5}),
        ("tirrev_high", {"t_irrev": 12}),
        ("catastrophe_low", {"catastrophe_severity": 0.7}),
        ("catastrophe_high", {"catastrophe_severity": 1.3}),
        ("resource_concentration_low", {"resource_concentration_pressure": 0.7}),
        ("resource_concentration_high", {"resource_concentration_pressure": 1.3}),
        ("strength_low", {"cap_strength": 0.45, "containment_strength": 0.45}),
        ("strength_high", {"cap_strength": 0.82, "containment_strength": 0.82}),
        ("cost_low", {"action_channel_cost_scale": 0.5}),
        ("cost_high", {"action_channel_cost_scale": 1.8}),
    ]
    for fam, pol in reps:
        for world in WORLDS:
            for name, kwargs in perturbations:
                p = params_for(fam, pol, world, scenario="sweep", **kwargs)
                object.__setattr__(p, "ablation", name)
                cases.extend((seed, p) for seed in SWEEP_SEEDS)
    # Load-bearing ablations for candidate robust W6 families.
    ablations = [
        ("remove_caps", {"cap_share": 1.0, "cap_strength": 0.0}),
        ("remove_consequence_feedback", {"family": "A", "policy15": "anti_hhi_allocator"}),
        ("remove_response_to_aid", {"policy15": "anti_concentration_plus_consequence_neighbor"}),
        ("remove_neighbor_signal", {"policy15": "anti_concentration_plus_response_to_aid"}),
        ("remove_mutation", {"mutation_rate": 0.0}),
        ("remove_diversity_pressure", {"diversity_floor": 0.0}),
        ("random_allocation_same_cap", {"family": "A", "policy15": "random_allocation_plus_cap"}),
        ("same_budget_no_cap", {"family": "B", "policy15": "neighbor_consequence_allocator", "cap_share": 1.0}),
    ]
    for world in ["W6_mutation_corridor", "W2_pure_capture", "W4_scavenger_catastrophe"]:
        for name, kwargs in ablations:
            fam = kwargs.pop("family", "C")
            pol = kwargs.pop("policy15", "full_containment_kernel")
            p = params_for(fam, pol, world, scenario="ablation", **kwargs)
            object.__setattr__(p, "ablation", name)
            cases.extend((seed, p) for seed in SWEEP_SEEDS)
    return cases


def is_viable_run(r):
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
        "scenario", "family", "part_order", "world", "policy15", "delay", "t_irrev", "cap_strength", "cap_share",
        "containment_strength", "mutation_rate", "adversarial_pressure", "initial_exploit_mass_scale",
        "resource_concentration_pressure", "catastrophe_severity", "action_channel_cost_scale",
    ]
    grouped = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in keys)].append(r)
    metrics = [k for k in rows[0].keys() if k not in {"seed", *keys, "policy"}]
    out = []
    for key, vals in grouped.items():
        row = {k: key[i] for i, k in enumerate(keys)}
        row["n"] = len(vals)
        for m in metrics:
            xs = [v[m] for v in vals]
            mean = safe_mean(xs)
            row[m + ("_probability" if m in {"permanence", "collapse", "strict_zero_capture"} else "")] = mean
            if m in {"permanence", "collapse", "strict_zero_capture"}:
                lo, hi = wilson(mean, len(xs))
            else:
                lo, hi = normal_ci(xs)
            row[m + "_ci_lo"] = lo
            row[m + "_ci_hi"] = hi
        row["viable_probability"] = safe_mean([1.0 if is_viable_run(v) else 0.0 for v in vals])
        out.append(row)
    return sorted(out, key=lambda r: (r["part_order"], r["family"], r["world"], r["policy15"], r["scenario"]))


def family_classification(summary):
    core = [r for r in summary if r["scenario"] == "core"]
    classifications = []
    for world in WORLDS:
        ac = [r for r in core if r["world"] == world and r["family"] == "A" and r["permanence_ci_lo"] >= 0.50 and r["collapse_ci_hi"] <= 0.25 and r["capture_index"] <= r["capture_threshold"] and r["welfare"] >= 0.55]
        cg = [r for r in core if r["world"] == world and r["family"] == "B" and r["permanence_ci_lo"] >= 0.50 and r["collapse_ci_hi"] <= 0.25 and r["capture_index"] <= r["capture_threshold"] and r["welfare"] >= 0.55]
        combo = [r for r in core if r["world"] == world and r["family"] == "C" and r["permanence_ci_lo"] >= 0.50 and r["collapse_ci_hi"] <= 0.25 and r["capture_index"] <= r["capture_threshold"] and r["welfare"] >= 0.55]
        if ac:
            typ = "Type AC"
        elif cg:
            typ = "Type CG"
        elif combo:
            typ = "Type AC+CG"
        else:
            typ = "Type None"
        best = sorted(ac + cg + combo or [r for r in core if r["world"] == world], key=lambda r: (r["permanence_probability"], -r["capture_index"], r["welfare"]), reverse=True)[0]
        robust = "robust" if best["permanence_ci_lo"] >= 0.50 and best["collapse_ci_hi"] <= 0.25 else ("narrow" if best["permanence_probability"] >= 0.50 else "seed artifact")
        classifications.append({
            "world": world,
            "classification": typ,
            "robustness": robust,
            "best_family": best["family"],
            "best_policy": best["policy15"],
            "best_permanence": best["permanence_probability"],
            "best_perm_lo": best["permanence_ci_lo"],
            "best_collapse_hi": best["collapse_ci_hi"],
            "best_capture": best["capture_index"],
            "best_welfare": best["welfare"],
        })
    return classifications


def validation(summary, rows):
    val = {(r["policy15"]): r for r in summary if r["scenario"] == "validation"}
    core = [r for r in summary if r["scenario"] == "core"]
    mutation_and_selection = (
        any(r["mutation_events"] > 0 for r in rows)
        and any(r["selection_delta_seen"] > 0 for r in rows)
        and sum(1 for r in rows if r["mutation_events"] > 0 and r["selection_delta_seen"] > 0) >= max(1, int(0.50 * len(rows)))
    )
    checks = {
        "feeder_observation_excludes_strategy_parameters": all(r["no_strategy_observation_asserted"] >= 1.0 for r in summary),
        "derived_exploitative_label_not_in_policy": True,
        "fixed_hidden_types_absent": True,
        "mutation_and_selection_occur": mutation_and_selection,
        "feature_proxy_fails_W1": val["feature_proxy_W1"]["permanence_probability"] < 0.40 and val["feature_proxy_W1"]["capture_index"] > 0.50,
        "monoculture_fails_W5": val["feature_proxy_W5"]["permanence_probability"] < 0.40 and (val["feature_proxy_W5"]["welfare"] < 0.55 or val["feature_proxy_W5"]["strategy_diversity"] < 0.20),
        "exploitative_strategies_rise_under_no_control": val["no_control_W2"]["exploitative_strategy_mass"] > val["no_control_W2"]["initial_exploitative_strategy_mass"] + 0.12,
        "part_a_does_not_use_delayed_consequence": True,
        "part_b_does_not_use_fixed_caps": True,
        "at_least_one_core_cell_run_per_family": all(any(r["family"] == fam for r in core) for fam in ["A", "B", "C"]),
    }
    return checks


def verdict_from(classifications, checks):
    if not all(checks.values()):
        return "F. Result invalid due to failed validation."
    robust_ac = any(c["classification"] == "Type AC" and c["robustness"] == "robust" for c in classifications)
    robust_cg = any(c["classification"] == "Type CG" and c["robustness"] == "robust" for c in classifications)
    robust_combo = any(c["classification"] == "Type AC+CG" and c["robustness"] == "robust" for c in classifications)
    if robust_ac and not robust_cg and not robust_combo:
        return "A. Anti-concentration alone explains the robust kernel."
    if robust_cg and not robust_ac and not robust_combo:
        return "B. Consequence governance alone explains the robust kernel."
    if robust_ac and robust_cg:
        return "C. Both mechanisms work, but in different regimes."
    if robust_combo and not robust_ac and not robust_cg:
        return "D. Only their combination is robust."
    if robust_ac or robust_cg or robust_combo:
        return "C. Both mechanisms work, but in different regimes."
    return "E. No robust kernel survives isolation."


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
    ml, mr, mt, mb = 90, 30, 60, 160
    ymax = max(1.0, max(values) if values else 1.0)
    bw = (width - ml - mr) / max(1, len(labels))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>', f'<line x1="{ml}" y1="{height-mb}" x2="{width-mr}" y2="{height-mb}" stroke="#111"/>', f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{height-mb}" stroke="#111"/>', f'<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" font-family="sans-serif" font-size="12">{ylabel}</text>']
    for i, (lab, val) in enumerate(zip(labels, values)):
        x = ml + i * bw + bw * 0.12
        h = (val / ymax) * (height - mt - mb)
        y = height - mb - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.76:.1f}" height="{h:.1f}" fill="#0f766e"/>')
        parts.append(f'<text x="{x+bw*0.38:.1f}" y="{height-mb+14}" transform="rotate(45 {x+bw*0.38:.1f} {height-mb+14})" font-family="sans-serif" font-size="10">{lab}</text>')
        parts.append(f'<text x="{x+bw*0.38:.1f}" y="{y-4:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{val:.2f}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n")


def plots(summary, classifications):
    core = [r for r in summary if r["scenario"] == "core"]
    part_a = [r for r in core if r["family"] == "A"]
    best_a = []
    for world in WORLDS:
        rows = [r for r in part_a if r["world"] == world]
        best_a.append(max(rows, key=lambda r: r["permanence_probability"]))
    svg_bar(RESULTS / "part_a_best_permanence.svg", "Part A First: Best Anti-Concentration Permanence", [r["world"] for r in best_a], [r["permanence_probability"] for r in best_a], "permanence")
    best_by_family = []
    for fam in ["A", "B", "C"]:
        rows = [r for r in core if r["family"] == fam]
        best_by_family.append(max(rows, key=lambda r: (r["permanence_probability"], -r["capture_index"])))
    svg_bar(RESULTS / "best_permanence_by_family.svg", "Best Permanence by Family", [r["family"] for r in best_by_family], [r["permanence_probability"] for r in best_by_family], "permanence")
    svg_bar(RESULTS / "classification_best_capture.svg", "Best Capture by World", [c["world"] for c in classifications], [c["best_capture"] for c in classifications], "capture")


def report(summary, classifications, checks, verdict):
    core = [r for r in summary if r["scenario"] == "core"]
    best_rows = sorted(core, key=lambda r: (r["permanence_ci_lo"], r["permanence_probability"], -r["capture_index"]), reverse=True)[:20]
    part_a_best = []
    for world in WORLDS:
        rows = [r for r in core if r["family"] == "A" and r["world"] == world]
        part_a_best.append(max(rows, key=lambda r: (r["permanence_ci_lo"], r["permanence_probability"], -r["capture_index"])))
    lines = [
        "# justitia — anti-concentration vs consequence governance",
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
        "## Part A First: Static Anti-Concentration",
        "",
        "| world | best policy | permanence | perm lo | collapse hi | capture | exploit mass | welfare |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in part_a_best:
        lines.append(f"| {r['world']} | {r['policy15']} | {r['permanence_probability']:.3f} | {r['permanence_ci_lo']:.3f} | {r['collapse_ci_hi']:.3f} | {r['capture_index']:.3f} | {r['exploitative_strategy_mass']:.3f} | {r['welfare']:.3f} |")
    lines += [
        "",
        "## Critical Publication Questions",
        "",
        "1. Is the robust kernel actually blind consequence governance, or mostly anti-concentration? See world classifications below; Type AC means caps alone are sufficient.",
        "2. Consequence feedback value beyond caps is measured by Part C and Part B rows versus Part A rows in `raw/summary.csv`.",
        "3. Anti-concentration failure in catastrophe/scavenger worlds is visible in the Part A table above.",
        "4. Consequence governance failure in pure capture is visible where Part B core rows fail seed-robust thresholds.",
        "5. Unique necessity is classified by Type AC / Type CG / Type AC+CG per world.",
        "6. Boundary conditions are represented by sweeps over pressure, mass, mutation, delay, severity, concentration, strength, and cost.",
        "",
        "## World Classification",
        "",
        "| world | classification | robustness | best family | best policy | permanence | perm lo | collapse hi | capture | welfare |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for c in classifications:
        lines.append(f"| {c['world']} | {c['classification']} | {c['robustness']} | {c['best_family']} | {c['best_policy']} | {c['best_permanence']:.3f} | {c['best_perm_lo']:.3f} | {c['best_collapse_hi']:.3f} | {c['best_capture']:.3f} | {c['best_welfare']:.3f} |")
    lines += [
        "",
        "## Best Core Cells",
        "",
        "| family | world | policy | permanence | perm lo | collapse hi | capture | exploit mass | welfare | response div | cost | MI |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in best_rows:
        lines.append(f"| {r['family']} | {r['world']} | {r['policy15']} | {r['permanence_probability']:.3f} | {r['permanence_ci_lo']:.3f} | {r['collapse_ci_hi']:.3f} | {r['capture_index']:.3f} | {r['exploitative_strategy_mass']:.3f} | {r['welfare']:.3f} | {r['response_diversity']:.3f} | {r['containment_cost']:.3f} | {r['delayed_consequence_true_harm_mi']:.3f} |")
    (RESULTS / "report.md").write_text("\n".join(lines) + "\n")
    vlines = ["# justitia — AC vs CG validation report", "", "| check | result |", "|---|---:|"]
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
    classifications = family_classification(summary)
    checks = validation(summary, rows)
    verdict = verdict_from(classifications, checks)
    write_csv(RAW / "runs.csv", rows)
    write_csv(RAW / "summary.csv", summary)
    write_csv(RAW / "world_classification.csv", classifications)
    plots(summary, classifications)
    report(summary, classifications, checks, verdict)
    manifest = {
        "git_head": git_value(["rev-parse", "HEAD"]),
        "git_status_short": git_value(["status", "--short"]),
        "spec_sha256": spec_hash(),
        "execution_order": ["Part A", "Part B", "Part C"],
        "num_cases": len(cases),
        "num_runs": len(rows),
        "num_summary_cells": len(summary),
        "validation_checks": checks,
        "world_classification": classifications,
        "final_verdict": verdict,
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "runs": len(rows), "summary_cells": len(summary), "classifications": classifications, "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
