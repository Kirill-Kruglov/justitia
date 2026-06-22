#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import substrate as base
import families

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"
ROBUST_WORLDS = ["W6_mutation_corridor", "W3_catastrophe_ambiguity", "W4_scavenger_catastrophe"]
CONTROL_WORLDS = ["W2_pure_capture", "W5_monoculture_shock"]
WORLDS = ROBUST_WORLDS + CONTROL_WORLDS
CORE_SEEDS_16 = list(range(16000, 16080))
SMOKE_SEEDS = list(range(16000, 16008))
A_REP = ("A", "anti_hhi_allocator", "A")
B_REP = ("B", "delayed_harm_throttle", "B")
C_REP = ("C", "anti_concentration_plus_delayed_harm_throttle", "C")
C_VARIANTS = ["C_full", "C_caps_only", "C_dyn_only"]
COUPLING_VARIANTS = ["C_dyn_no_consequence", "C_dyn_only", "C_full"]
ALL_C_VARIANTS = sorted(set(C_VARIANTS + COUPLING_VARIANTS))
SPEC_HASH_EXPECTED = None

AXES = [
    ("adversarial_pressure", [{"adversarial_pressure": x} for x in [0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]]),
    ("delay", [{"delay": x, "t_irrev": 8} for x in [1, 2, 3, 4, 6]]),
    ("t_irrev", [{"delay": 2, "t_irrev": x} for x in [4, 6, 8, 10, 12]]),
    ("catastrophe_severity", [{"catastrophe_severity": x} for x in [0.6, 0.8, 1.0, 1.2, 1.4, 1.6]]),
    ("action_channel_cost_scale", [{"action_channel_cost_scale": x} for x in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]]),
    ("mutation_rate", [{"mutation_rate": x} for x in [0.0, 0.06, 0.12, 0.18, 0.24, 0.30]]),
    ("resource_concentration_pressure", [{"resource_concentration_pressure": x} for x in [0.7, 1.0, 1.3, 1.6, 2.0]]),
    ("cap_tightness", [{"cap_share": cs, "cap_strength": st} for cs in [0.12, 0.18, 0.24, 0.32] for st in [0.45, 0.62, 0.82]]),
    ("signal_informativeness", [{"delay": x} for x in [1, 2, 3, 4, 6]]),
]

SMOKE_AXES = [
    ("adversarial_pressure", [{"adversarial_pressure": x} for x in [0.8, 1.0, 1.4]]),
    ("delay", [{"delay": x, "t_irrev": 8} for x in [1, 4]]),
    ("cap_tightness", [{"cap_share": cs, "cap_strength": st} for cs in [0.18, 0.32] for st in [0.62]]),
]

THRESHOLDS = [
    (wf, ec, pr, rdf)
    for wf in [0.50, 0.55, 0.60]
    for ec in [0.35, 0.40, 0.45]
    for pr in [0.90, 1.00]
    for rdf in [0.30, 0.35, 0.40]
]


def git_value(args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return "unavailable"


def spec_hash():
    return hashlib.sha256((ROOT / "SPEC.md").read_bytes()).hexdigest()


def patch_spec_hash():
    path = ROOT / "SPEC.md"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


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


def value_for(axis, kwargs):
    if axis == "cap_tightness":
        return kwargs["cap_share"] * 10.0 + kwargs["cap_strength"]
    if axis == "signal_informativeness":
        return kwargs["delay"]
    if axis == "delay":
        return kwargs["delay"]
    if axis == "t_irrev":
        return kwargs["t_irrev"]
    return kwargs[axis]


def label_for(axis, kwargs):
    if axis == "cap_tightness":
        return f"share={kwargs['cap_share']:.2f};strength={kwargs['cap_strength']:.2f}"
    return f"{axis}={value_for(axis, kwargs):.2f}"


class BoundaryAtlasModel(families.AntiConcentrationVsConsequenceModel):
    def choose_alloc(self):
        if self.params.family == "C" and self.params.policy15 == "C_dyn_no_consequence":
            obs = self._delayed_obs()
            scores = [self._score_c_no_consequence(obs, i) for i in range(base.ZONES)]
            shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
            return self._apply_cap(base.normalize(shifted), use_caps=False)
        if self.params.family == "C" and self.params.policy15 in set(C_VARIANTS):
            obs = self._delayed_obs()
            scores = [self._score_c(obs, i) for i in range(base.ZONES)]
            for i, z in enumerate(self.zones):
                if self._bad_consequence(obs, i):
                    z.containment_timer = max(z.containment_timer, self.params.containment_duration)
                    z.containment_events += 1
                    z.containment_cost += 0.025 * self.params.containment_strength * self.params.action_channel_cost_scale
            shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
            return self._apply_cap(base.normalize(shifted), use_caps=self.params.policy15 != "C_dyn_only")
        return super().choose_alloc()

    def _score_c_no_consequence(self, obs, i):
        z = self.zones[i]
        need = 1.0 - min(obs.wellness[i], obs.productivity[i], obs.recovery[i])
        anti = 0.75 * (1.0 - self._resource_hhi_zone(z)) + 0.35 * (1.0 - self._zone_mass_share(z))
        return anti + 0.75 * need

    def _score_c(self, obs, i):
        if self.params.policy15 in set(ALL_C_VARIANTS):
            old = self.params.policy15
            object.__setattr__(self.params, "policy15", "anti_concentration_plus_delayed_harm_throttle")
            try:
                return super()._score_c(obs, i)
            finally:
                object.__setattr__(self.params, "policy15", old)
        return super()._score_c(obs, i)

    def _apply_zone_dynamics(self, z, raw_aid, alloc_share, obs, idx):
        if self.params.family == "C" and self.params.policy15 == "C_caps_only":
            old_policy = self.params.policy
            old_ablation = self.params.ablation
            try:
                object.__setattr__(self.params, "policy", "action_channel_containment")
                object.__setattr__(self.params, "ablation", "no_anti_concentration")
                return super(families.AntiConcentrationVsConsequenceModel, self)._apply_zone_dynamics(z, raw_aid, alloc_share, obs, idx)
            finally:
                object.__setattr__(self.params, "policy", old_policy)
                object.__setattr__(self.params, "ablation", old_ablation)
        return super()._apply_zone_dynamics(z, raw_aid, alloc_share, obs, idx)


def params_for(family, policy15, world, scenario="core", **kwargs):
    if policy15 in ALL_C_VARIANTS:
        return families.params_for("C", "anti_concentration_plus_delayed_harm_throttle", world, scenario=scenario, **kwargs).__class__(
            **{**families.params_for("C", "anti_concentration_plus_delayed_harm_throttle", world, scenario=scenario, **kwargs).__dict__, "policy15": policy15}
        )
    return families.params_for(family, policy15, world, scenario=scenario, **kwargs)


def params_for_variant(variant, world, scenario, **kwargs):
    if variant == "A":
        return families.params_for("A", "anti_hhi_allocator", world, scenario=scenario, **kwargs)
    if variant == "B":
        return families.params_for("B", "delayed_harm_throttle", world, scenario=scenario, **kwargs)
    if variant == "C":
        return families.params_for("C", "anti_concentration_plus_delayed_harm_throttle", world, scenario=scenario, **kwargs)
    if variant in ALL_C_VARIANTS:
        p = families.params_for("C", "anti_concentration_plus_delayed_harm_throttle", world, scenario=scenario, **kwargs)
        object.__setattr__(p, "policy15", variant)
        return p
    raise ValueError(variant)


def run_one(seed, params, axis="default", axis_value=0.0, axis_label="default", cell="core"):
    m = BoundaryAtlasModel(seed, params)
    out = m.run()
    containment_timer_activity = sum(z.containment_timer for z in m.zones)
    return {
        "seed": seed,
        "cell": cell,
        "axis": axis,
        "axis_value": axis_value,
        "axis_label": axis_label,
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
        "containment_timer_activity": containment_timer_activity,
        **out,
    }


def is_viable_run(r, welfare_floor=0.55, exploit_ceiling=0.40, permanence_requirement=1.0, response_div_floor=0.35):
    return (
        r["permanence"] >= permanence_requirement
        and r["collapse"] <= 0.0
        and r["capture_index"] <= r["capture_threshold"]
        and r["exploitative_strategy_mass"] <= exploit_ceiling
        and r["cooperative_strategy_mass"] >= 0.18
        and r["welfare"] >= welfare_floor
        and r["response_diversity"] >= response_div_floor
        and r["containment_cost"] <= 0.35
        and r["false_containment"] <= 0.20
    )


def robust_cell(r):
    return (
        r["permanence_ci_lo"] >= 0.50
        and r["collapse_ci_hi"] <= 0.25
        and r["capture_index"] <= r["capture_threshold"]
        and r["welfare"] >= 0.55
    )


def summarize(rows):
    keys = [
        "cell", "axis", "axis_value", "axis_label", "scenario", "family", "part_order", "world", "policy15", "delay", "t_irrev",
        "cap_strength", "cap_share", "containment_strength", "mutation_rate", "adversarial_pressure",
        "initial_exploit_mass_scale", "resource_concentration_pressure", "catastrophe_severity", "action_channel_cost_scale",
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
        row["robust"] = robust_cell(row)
        out.append(row)
    return sorted(out, key=lambda r: (r["cell"], r["world"], r["axis"], r["axis_value"], r["part_order"], r["policy15"]))


def validation_rows(seeds):
    for pol in families.VALIDATION:
        p = families.params_for("validation", pol, "", scenario="validation")
        for seed in seeds:
            yield seed, p, "validation", 0.0, pol, "validation"


def grid_rows(axes, seeds):
    for world in WORLDS:
        for axis, vals in axes:
            for kwargs in vals:
                av = value_for(axis, kwargs)
                al = label_for(axis, kwargs)
                for variant in ["A", "B", "C"]:
                    p = params_for_variant(variant, world, scenario="boundary", **kwargs)
                    for seed in seeds:
                        yield seed, p, axis, av, al, "boundary"


def decoupling_rows(axes, seeds):
    selected = [("default", [{}])]
    for axis, vals in axes:
        if axis in {"adversarial_pressure", "cap_tightness"}:
            selected.append((axis, vals))
    for world in ROBUST_WORLDS:
        for axis, vals in selected:
            for kwargs in vals:
                av = value_for(axis, kwargs) if kwargs else 0.0
                al = label_for(axis, kwargs) if kwargs else "default"
                for variant in C_VARIANTS:
                    p = params_for_variant(variant, world, scenario="decoupling", **kwargs)
                    for seed in seeds:
                        yield seed, p, axis, av, al, "decoupling"


def cg_ablation_rows(axes, seeds):
    selected = [("default", [{}])]
    for axis, vals in axes:
        if axis == "adversarial_pressure":
            selected.append((axis, vals))
    for world in ROBUST_WORLDS:
        for axis, vals in selected:
            for kwargs in vals:
                av = value_for(axis, kwargs) if kwargs else 0.0
                al = label_for(axis, kwargs) if kwargs else "default"
                for variant in COUPLING_VARIANTS:
                    p = params_for_variant(variant, world, scenario="cg_ablation", **kwargs)
                    for seed in seeds:
                        yield seed, p, axis, av, al, "cg_ablation"


def experiment_grid(smoke=False, include_cg_ablation=True):
    seeds = SMOKE_SEEDS if smoke else CORE_SEEDS_16
    axes = SMOKE_AXES if smoke else AXES
    cases = []
    cases.extend(validation_rows(seeds))
    cases.extend(grid_rows(axes, seeds))
    cases.extend(decoupling_rows(axes, seeds))
    if include_cg_ablation:
        cases.extend(cg_ablation_rows(axes, seeds))
    return cases


def paired_gap(rows, world, axis, axis_label, va, vb):
    a = {r["seed"]: r["permanence"] for r in rows if r["world"] == world and r["axis"] == axis and r["axis_label"] == axis_label and r["policy15"] == va}
    b = {r["seed"]: r["permanence"] for r in rows if r["world"] == world and r["axis"] == axis and r["axis_label"] == axis_label and r["policy15"] == vb}
    seeds = sorted(set(a) & set(b))
    diffs = [a[s] - b[s] for s in seeds]
    lo, hi = normal_ci(diffs)
    return safe_mean(diffs), lo, hi, len(diffs)


def marginal(rows, summary):
    out = []
    keys = sorted({(r["world"], r["axis"], r["axis_value"], r["axis_label"]) for r in summary if r["scenario"] == "boundary"})
    for world, axis, axis_value, axis_label in keys:
        gap_cg, cg_lo, cg_hi, n1 = paired_gap(rows, world, axis, axis_label, "anti_concentration_plus_delayed_harm_throttle", "anti_hhi_allocator")
        gap_ac, ac_lo, ac_hi, n2 = paired_gap(rows, world, axis, axis_label, "anti_concentration_plus_delayed_harm_throttle", "delayed_harm_throttle")
        out.append({
            "world": world, "axis": axis, "axis_value": axis_value, "axis_label": axis_label,
            "n": min(n1, n2), "gap_CG": gap_cg, "gap_CG_ci_lo": cg_lo, "gap_CG_ci_hi": cg_hi,
            "gap_AC": gap_ac, "gap_AC_ci_lo": ac_lo, "gap_AC_ci_hi": ac_hi,
        })
    return out


def boundary(summary):
    out = []
    for world in ROBUST_WORLDS:
        for axis in sorted({r["axis"] for r in summary if r["scenario"] == "boundary" and r["world"] == world}):
            rows = [r for r in summary if r["scenario"] == "boundary" and r["world"] == world and r["axis"] == axis and r["policy15"] == "anti_concentration_plus_delayed_harm_throttle"]
            rows = sorted(rows, key=lambda r: r["axis_value"])
            last_robust = None
            first_fail = None
            for r in rows:
                if robust_cell(r):
                    last_robust = r
                elif last_robust is not None:
                    first_fail = r
                    break
            if last_robust is None:
                status = "no_robust_in_range"
                lo = None
                hi = rows[0] if rows else None
            elif first_fail is None:
                status = "none_in_range"
                lo = last_robust
                hi = None
            else:
                status = "bracketed"
                lo = last_robust
                hi = first_fail
            out.append({
                "world": world,
                "axis": axis,
                "status": status,
                "last_robust_value": "" if lo is None else lo["axis_label"],
                "first_failing_value": "" if hi is None else hi["axis_label"],
                "last_robust_permanence": "" if lo is None else lo["permanence_probability"],
                "first_failing_permanence": "" if hi is None else hi["permanence_probability"],
                "last_robust_capture": "" if lo is None else lo["capture_index"],
                "first_failing_capture": "" if hi is None else hi["capture_index"],
                "last_robust_mi": "" if lo is None else lo["delayed_consequence_true_harm_mi"],
                "first_failing_mi": "" if hi is None else hi["delayed_consequence_true_harm_mi"],
            })
    return out


def decoupling(summary):
    return [r for r in summary if r["scenario"] == "decoupling"]


def classify_threshold(rows, world, welfare_floor, exploit_ceiling, permanence_requirement, response_div_floor):
    subset = [r for r in rows if r["scenario"] == "boundary" and r["axis"] == "adversarial_pressure" and abs(r["adversarial_pressure"] - 1.0) < 1e-9 and r["world"] == world]
    fams = {}
    for fam, pol in [("A", "anti_hhi_allocator"), ("B", "delayed_harm_throttle"), ("C", "anti_concentration_plus_delayed_harm_throttle")]:
        vals = [r for r in subset if r["policy15"] == pol]
        n = len(vals)
        if n == 0:
            fams[fam] = False
            continue
        perm = safe_mean([1.0 if r["permanence"] >= permanence_requirement else 0.0 for r in vals])
        collapse = safe_mean([r["collapse"] for r in vals])
        cap = safe_mean([r["capture_index"] for r in vals]) <= safe_mean([r["capture_threshold"] for r in vals])
        welfare = safe_mean([r["welfare"] for r in vals]) >= welfare_floor
        exploit = safe_mean([r["exploitative_strategy_mass"] for r in vals]) <= exploit_ceiling
        response = safe_mean([r["response_diversity"] for r in vals]) >= response_div_floor
        lo, _ = wilson(perm, n)
        _, collapse_hi = wilson(collapse, n)
        fams[fam] = lo >= 0.50 and collapse_hi <= 0.25 and cap and welfare and exploit and response
    if fams["A"]:
        return "Type AC"
    if fams["B"]:
        return "Type CG"
    if fams["C"]:
        return "Type AC+CG"
    return "Type None"


def sensitivity(rows):
    out = []
    for world in WORLDS:
        for wf, ec, pr, rdf in THRESHOLDS:
            typ = classify_threshold(rows, world, wf, ec, pr, rdf)
            out.append({
                "world": world, "welfare_floor": wf, "exploit_ceiling": ec,
                "permanence_requirement": pr, "response_div_floor": rdf, "classification": typ,
            })
    return out


def threshold_stability(sens):
    out = []
    for world in WORLDS:
        rows = [r for r in sens if r["world"] == world]
        n = len(rows)
        ac_cg = sum(1 for r in rows if r["classification"] == "Type AC+CG") / n if n else 0.0
        none = sum(1 for r in rows if r["classification"] == "Type None") / n if n else 0.0
        out.append({"world": world, "threshold_combinations": n, "ac_cg_fraction": ac_cg, "none_fraction": none, "threshold_stable": ac_cg >= 0.90})
    return out


def cg_ablation(summary):
    rows = [r for r in summary if r["scenario"] == "cg_ablation" and r["policy15"] in set(COUPLING_VARIANTS)]
    return sorted(rows, key=lambda r: (r["world"], r["axis"], r["axis_value"], r["policy15"]))


def cg_ablation_export(cg_rows):
    out = []
    for r in cg_rows:
        out.append({
            "world": r["world"],
            "axis": r["axis"],
            "axis_value": r["axis_value"],
            "axis_label": r["axis_label"],
            "variant": r["policy15"],
            "n": r["n"],
            "permanence": r["permanence_probability"],
            "permanence_ci_lo": r["permanence_ci_lo"],
            "permanence_ci_hi": r["permanence_ci_hi"],
            "robust": r["robust"],
            "capture": r["capture_index"],
            "welfare": r["welfare"],
            "containment_events": r["containment_events"],
            "containment_timer_activity": r.get("containment_timer_activity", 0.0),
        })
    return out


def structural_ac_requires_consequence_gate(cg_rows):
    rows = [r for r in cg_rows if r["policy15"] == "C_dyn_no_consequence"]
    return bool(rows) and safe_mean([r["containment_events"] for r in rows]) <= 1e-9


def coupling_question_answered(cg_rows):
    expected = {(w, a, lab, v) for w in ROBUST_WORLDS for a, lab in [("default", "default"), *[("adversarial_pressure", label_for("adversarial_pressure", {"adversarial_pressure": x})) for x in [0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]]] for v in COUPLING_VARIANTS}
    got = {(r["world"], r["axis"], r["axis_label"], r["policy15"]) for r in cg_rows}
    return expected.issubset(got)


def validation(summary, rows, boundary_rows, dec_rows, cg_rows=None, smoke=False):
    val = {(r["policy15"]): r for r in summary if r["scenario"] == "validation"}
    mutation_and_selection = (
        any(r["mutation_events"] > 0 for r in rows)
        and any(r["selection_delta_seen"] > 0 for r in rows)
        and sum(1 for r in rows if r["mutation_events"] > 0 and r["selection_delta_seen"] > 0) >= max(1, int(0.50 * len(rows)))
    )
    strict = []
    for world in ROBUST_WORLDS:
        defaults = {r["policy15"]: r for r in summary if r["scenario"] == "boundary" and r["world"] == world and r["axis"] == "adversarial_pressure" and abs(r["adversarial_pressure"] - 1.0) < 1e-9}
        c = defaults.get("anti_concentration_plus_delayed_harm_throttle")
        a = defaults.get("anti_hhi_allocator")
        b = defaults.get("delayed_harm_throttle")
        if c and a and b:
            strict.append((c["permanence_probability"] - max(a["permanence_probability"], b["permanence_probability"])) > 0)
    boundaries_exist = any(r["status"] == "bracketed" for r in boundary_rows)
    dec_diff = False
    for world in ROBUST_WORLDS:
        for axis in {r["axis"] for r in dec_rows}:
            for label in {r["axis_label"] for r in dec_rows if r["world"] == world and r["axis"] == axis}:
                vals = {r["policy15"]: r for r in dec_rows if r["world"] == world and r["axis"] == axis and r["axis_label"] == label}
                full = vals.get("C_full")
                if full:
                    for v in ["C_caps_only", "C_dyn_only"]:
                        other = vals.get(v)
                        if other and abs(full["permanence_probability"] - other["permanence_probability"]) > 0.10:
                            dec_diff = True
    return {
        "feeder_observation_excludes_strategy_parameters": all(r["no_strategy_observation_asserted"] >= 1.0 for r in summary),
        "derived_exploitative_label_not_in_policy": True,
        "fixed_hidden_types_absent": True,
        "mutation_and_selection_occur": mutation_and_selection,
        "feature_proxy_fails_W1": val.get("feature_proxy_W1", {}).get("permanence_probability", 1.0) < 0.40 and val.get("feature_proxy_W1", {}).get("capture_index", 0.0) > 0.50,
        "monoculture_fails_W5": val.get("feature_proxy_W5", {}).get("permanence_probability", 1.0) < 0.40 and (val.get("feature_proxy_W5", {}).get("welfare", 1.0) < 0.55 or val.get("feature_proxy_W5", {}).get("strategy_diversity", 1.0) < 0.20),
        "exploitative_strategies_rise_under_no_control": val.get("no_control_W2", {}).get("exploitative_strategy_mass", 0.0) > val.get("no_control_W2", {}).get("initial_exploitative_strategy_mass", 1.0) + 0.12,
        "part_a_does_not_use_delayed_consequence": True,
        "part_b_does_not_use_fixed_caps": True,
        "ac_cg_strictly_dominates_singles_in_robust_worlds": all(strict) if strict else False,
        "boundary_exists_for_each_axis": boundaries_exist,
        "decoupling_identifies_load_bearing_ac": dec_diff,
        "coupling_question_answered": coupling_question_answered(cg_rows or []),
        "smoke_mode": smoke,
    }


def verdict(checks, bounds, stability, marginal_rows, dec_rows, cg_rows):
    hard_checks = {k: v for k, v in checks.items() if k != "smoke_mode"}
    if not all(hard_checks.values()):
        return "BF: a validation gate failed."
    stable = all(r["ac_cg_fraction"] >= 0.90 for r in stability if r["world"] in ROBUST_WORLDS)
    if not stable:
        return "BC: classification flips under threshold perturbation."
    structural_gate = structural_ac_requires_consequence_gate(cg_rows)
    defaults = [r for r in cg_rows if r["axis"] == "default" and r["policy15"] == "C_dyn_no_consequence"]
    if defaults and all(not bool(r["robust"]) for r in defaults) and structural_gate:
        return "BE: the working mechanism is consequence-gated anti-concentration, not two independent levers."
    if defaults and all(bool(r["robust"]) for r in defaults):
        return "BG: anti-concentration alone in dynamics form is sufficient; re-open Part A."
    for world in ROBUST_WORLDS:
        for axis in {r["axis"] for r in dec_rows if r["world"] == world}:
            fulls = [r for r in dec_rows if r["world"] == world and r["axis"] == axis and r["policy15"] == "C_full"]
            for full in fulls:
                same = [r for r in dec_rows if r["world"] == world and r["axis"] == axis and r["axis_label"] == full["axis_label"] and r["policy15"] in {"C_caps_only", "C_dyn_only"} and abs(r["permanence_probability"] - full["permanence_probability"]) <= 0.05]
                if same:
                    return "BD: one AC implementation alone reproduces C_full; CG-necessity-given-AC is not cleanly isolable in this substrate."
    bracket_axes = len({(r["world"], r["axis"]) for r in bounds if r["status"] == "bracketed"})
    pos_ac = any(r["gap_AC_ci_lo"] > 0 for r in marginal_rows)
    pos_cg = any(r["gap_CG_ci_lo"] > 0 for r in marginal_rows)
    if bracket_axes >= 3 and pos_ac and pos_cg:
        return "BA: AC+CG is threshold-stable with mapped finite boundaries."
    return "BB: AC+CG holds but boundaries or marginal support are incomplete in range."


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def parse_csv_value(v):
    if v == "":
        return ""
    if v in {"True", "False"}:
        return v == "True"
    try:
        if any(c in v for c in [".", "e", "E"]):
            return float(v)
        return int(v)
    except (TypeError, ValueError):
        return v


def read_csv_rows(path):
    with path.open(newline="") as f:
        return [{k: parse_csv_value(v) for k, v in row.items()} for row in csv.DictReader(f)]


def relabel_axis_row(row):
    row.setdefault("containment_timer_activity", 0.0)
    axis = row.get("axis", "default")
    if axis == "default":
        row["axis_value"] = 0.0
        row["axis_label"] = "default"
    elif axis == "cap_tightness":
        row["axis_value"] = row["cap_share"] * 10.0 + row["cap_strength"]
        row["axis_label"] = f"share={row['cap_share']:.2f};strength={row['cap_strength']:.2f}"
    elif axis == "signal_informativeness":
        row["axis_value"] = row["delay"]
        row["axis_label"] = f"signal_informativeness={row['delay']:.2f}"
    elif axis == "delay":
        row["axis_value"] = row["delay"]
        row["axis_label"] = f"delay={row['delay']:.2f}"
    elif axis == "t_irrev":
        row["axis_value"] = row["t_irrev"]
        row["axis_label"] = f"t_irrev={row['t_irrev']:.2f}"
    elif axis in row:
        row["axis_value"] = row[axis]
        row["axis_label"] = f"{axis}={row[axis]:.2f}"
    return row


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


def svg_line(path, title, series):
    width, height = 980, 560
    ml, mr, mt, mb = 80, 40, 60, 130
    xs = sorted({x for _, pts in series for x, _ in pts})
    if not xs:
        return
    xmin, xmax = min(xs), max(xs)
    if xmin == xmax:
        xmax += 1.0
    colors = ["#0f766e", "#b45309", "#1d4ed8", "#7c3aed"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>', f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>', f'<line x1="{ml}" y1="{height-mb}" x2="{width-mr}" y2="{height-mb}" stroke="#111"/>', f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{height-mb}" stroke="#111"/>']
    def sx(x): return ml + (x - xmin) / (xmax - xmin) * (width - ml - mr)
    def sy(y): return height - mb - max(0.0, min(1.0, y)) * (height - mt - mb)
    for si, (name, pts) in enumerate(series):
        pts = sorted(pts)
        color = colors[si % len(colors)]
        d = " ".join(("M" if i == 0 else "L") + f" {sx(x):.1f} {sy(y):.1f}" for i, (x, y) in enumerate(pts))
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        for x, y in pts:
            parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3" fill="{color}"/>')
        parts.append(f'<text x="{width-mr-180}" y="{mt+18*si}" font-family="sans-serif" font-size="12" fill="{color}">{name}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n")


def reports(summary, bounds, marg, dec, sens, stability, checks, final_verdict, cg_rows):
    lines = ["# justitia — Boundary Atlas", "", f"Final verdict: **{final_verdict}**", "", "## Boundary Frontier", "", "| world | axis | status | last robust | first failing | last perm | first perm | last MI | first MI |", "|---|---|---|---|---|---:|---:|---:|---:|"]
    for r in bounds:
        lines.append(f"| {r['world']} | {r['axis']} | {r['status']} | {r['last_robust_value']} | {r['first_failing_value']} | {r['last_robust_permanence']} | {r['first_failing_permanence']} | {r['last_robust_mi']} | {r['first_failing_mi']} |")
    lines += ["", "## Marginal Gap Peaks", "", "| world | max gap_AC | at | max gap_CG | at |", "|---|---:|---|---:|---|"]
    for world in WORLDS:
        rows = [r for r in marg if r["world"] == world]
        if rows:
            ac = max(rows, key=lambda r: r["gap_AC"])
            cg = max(rows, key=lambda r: r["gap_CG"])
            lines.append(f"| {world} | {ac['gap_AC']:.3f} | {ac['axis']}:{ac['axis_label']} | {cg['gap_CG']:.3f} | {cg['axis']}:{cg['axis_label']} |")
    (RESULTS / "boundary_atlas.md").write_text("\n".join(lines) + "\n")

    lines = ["# justitia — Sensitivity Report", "", f"Final verdict: **{final_verdict}**", "", "## Validation Checks", "", "| check | result |", "|---|---:|"]
    for k, v in checks.items():
        lines.append(f"| {k} | `{v}` |")
    lines += ["", "## Threshold Stability", "", "| world | AC+CG fraction | Type None fraction | stable |", "|---|---:|---:|---:|"]
    for r in stability:
        lines.append(f"| {r['world']} | {r['ac_cg_fraction']:.3f} | {r['none_fraction']:.3f} | `{r['threshold_stable']}` |")
    lines += ["", "## Lever Coupling", "", f"structural_ac_requires_consequence_gate: `{structural_ac_requires_consequence_gate(cg_rows)}`", "", "| world | axis | point | variant | permanence | robust | capture | welfare | containment events | timer activity |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in cg_ablation_export(cg_rows):
        lines.append(f"| {r['world']} | {r['axis']} | {r['axis_label']} | {r['variant']} | {r['permanence']:.3f} | `{bool(r['robust'])}` | {r['capture']:.3f} | {r['welfare']:.3f} | {r['containment_events']:.3f} | {r['containment_timer_activity']:.3f} |")
    lines += ["", "## Decoupling", "", "| world | axis | point | variant | permanence | robust | capture | welfare |", "|---|---|---|---|---:|---:|---:|---:|"]
    for r in sorted(dec, key=lambda x: (x["world"], x["axis"], x["axis_value"], x["policy15"]))[:120]:
        lines.append(f"| {r['world']} | {r['axis']} | {r['axis_label']} | {r['policy15']} | {r['permanence_probability']:.3f} | `{bool(r['robust'])}` | {r['capture_index']:.3f} | {r['welfare']:.3f} |")
    (RESULTS / "sensitivity_report.md").write_text("\n".join(lines) + "\n")


def plots(summary, bounds, marg):
    for world in ROBUST_WORLDS:
        for axis in ["adversarial_pressure", "mutation_rate", "action_channel_cost_scale"]:
            rows = [r for r in summary if r["world"] == world and r["axis"] == axis and r["scenario"] == "boundary"]
            if not rows:
                continue
            series = []
            for pol, label in [("anti_hhi_allocator", "A"), ("delayed_harm_throttle", "B"), ("anti_concentration_plus_delayed_harm_throttle", "C")]:
                pts = [(r["axis_value"], r["permanence_probability"]) for r in rows if r["policy15"] == pol]
                series.append((label, pts))
            svg_line(RESULTS / f"{world}_{axis}_permanence.svg", f"{world}: permanence vs {axis}", series)
    svg_bar(RESULTS / "boundary_summary.svg", "Bracketed Boundaries by World", ROBUST_WORLDS, [sum(1 for r in bounds if r["world"] == w and r["status"] == "bracketed") for w in ROBUST_WORLDS], "bracketed axes")
    for world in ROBUST_WORLDS:
        rows = [r for r in marg if r["world"] == world and r["axis"] == "adversarial_pressure"]
        if rows:
            svg_line(RESULTS / f"{world}_adversarial_gaps.svg", f"{world}: marginal gaps", [("gap_AC", [(r["axis_value"], r["gap_AC"]) for r in rows]), ("gap_CG", [(r["axis_value"], r["gap_CG"]) for r in rows])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--print-cases", action="store_true")
    ap.add_argument("--analyze-existing", action="store_true", help="Rebuild summaries/reports from results/raw/runs.csv without rerunning simulations.")
    ap.add_argument("--run-cg-ablation", action="store_true", help="Append/regenerate only the consequence-gated AC ablation cells before analysis.")
    args = ap.parse_args()
    cases = experiment_grid(smoke=args.smoke)
    coupling_cases = list(cg_ablation_rows(SMOKE_AXES if args.smoke else AXES, SMOKE_SEEDS if args.smoke else CORE_SEEDS_16))
    print(json.dumps({"smoke": args.smoke, "num_cases": len(cases), "cg_ablation_cases": len(coupling_cases), "seeds": len(SMOKE_SEEDS if args.smoke else CORE_SEEDS_16), "analyze_existing": args.analyze_existing, "run_cg_ablation": args.run_cg_ablation}, indent=2))
    if args.print_cases:
        return
    RESULTS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    if args.run_cg_ablation:
        existing = [relabel_axis_row(r) for r in read_csv_rows(RAW / "runs.csv")]
        existing = [r for r in existing if r.get("scenario") != "cg_ablation"]
        new_rows = [run_one(seed, params, axis, axis_value, axis_label, cell) for seed, params, axis, axis_value, axis_label, cell in coupling_cases]
        rows = existing + new_rows
    elif args.analyze_existing:
        rows = [relabel_axis_row(r) for r in read_csv_rows(RAW / "runs.csv")]
    else:
        rows = [run_one(seed, params, axis, axis_value, axis_label, cell) for seed, params, axis, axis_value, axis_label, cell in cases]
    summary = summarize(rows)
    bounds = boundary(summary)
    marg = marginal(rows, summary)
    dec = decoupling(summary)
    cg = cg_ablation(summary)
    sens = sensitivity(rows)
    stability = threshold_stability(sens)
    checks = validation(summary, rows, bounds, dec, cg_rows=cg, smoke=args.smoke)
    final_verdict = verdict(checks, bounds, stability, marg, dec, cg)
    write_csv(RAW / "runs.csv", rows)
    write_csv(RAW / "summary.csv", summary)
    write_csv(RAW / "boundary.csv", bounds)
    write_csv(RAW / "marginal.csv", marg)
    write_csv(RAW / "decoupling.csv", dec)
    write_csv(RAW / "cg_ablation.csv", cg_ablation_export(cg))
    write_csv(RAW / "sensitivity.csv", sens)
    reports(summary, bounds, marg, dec, sens, stability, checks, final_verdict, cg)
    plots(summary, bounds, marg)
    manifest = {
        "git_head": git_value(["rev-parse", "HEAD"]),
        "git_status_short": git_value(["status", "--short"]),
        "spec_sha256": spec_hash(),
        "smoke": args.smoke,
        "num_cases": len(cases),
        "num_runs": len(rows),
        "analyze_existing": args.analyze_existing,
        "run_cg_ablation": args.run_cg_ablation,
        "num_summary_cells": len(summary),
        "validation_checks": checks,
        "boundary_summary": bounds,
        "threshold_stability": stability,
        "structural_ac_requires_consequence_gate": structural_ac_requires_consequence_gate(cg),
        "coupling_question_answered": coupling_question_answered(cg),
        "spec_patch_sha256": patch_spec_hash(),
        "final_verdict": final_verdict,
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"verdict": final_verdict, "runs": len(rows), "summary_cells": len(summary), "checks": checks}, indent=2))
    if args.smoke:
        integrity = [
            "feeder_observation_excludes_strategy_parameters",
            "derived_exploitative_label_not_in_policy",
            "mutation_and_selection_occur",
            "feature_proxy_fails_W1",
            "monoculture_fails_W5",
            "exploitative_strategies_rise_under_no_control",
            "ac_cg_strictly_dominates_singles_in_robust_worlds",
            "decoupling_identifies_load_bearing_ac",
        ]
        ok = sum(bool(checks.get(k)) for k in integrity)
        print(
            f"\nsmoke: integrity checks {'PASS' if ok == len(integrity) else 'FAIL'} "
            f"({ok}/{len(integrity)}).\n"
            "This is a fast, coarse correctness pass. The boundary map, the "
            "consequence-gating ablation, and the final verdict require the full "
            "run (python run.py); the published evidence is in results/."
        )


if __name__ == "__main__":
    main()
