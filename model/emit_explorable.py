#!/usr/bin/env python3
"""Emit recorded trajectories for the static Justitia explorable.

The browser never simulates the substrate. It replays these JSON files, which are
recorded from the validated Python model with `record_trajectory=True`.
"""
import argparse
import json
import math
import statistics
from dataclasses import asdict
from pathlib import Path

import atlas
import substrate as base

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DATA = WEB / "data"
N_SEEDS = 24
SEEDS = list(range(16000, 16000 + N_SEEDS))
REP_SEED = SEEDS[0]
ROBUST_WORLDS = ["W6_mutation_corridor", "W3_catastrophe_ambiguity", "W4_scavenger_catastrophe"]
CONTROL_WORLDS = ["W2_pure_capture", "W5_monoculture_shock"]
WORLDS = ROBUST_WORLDS + CONTROL_WORLDS
BOUNDARY_PRESSURES = [0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8]
BAND_METRICS = [
    "welfare",
    "minimum_zone_welfare",
    "capture_index",
    "exploitative_strategy_mass",
    "cooperative_strategy_mass",
    "resource_hhi",
    "containment_events_this_step",
]


class Config:
    def __init__(self, config_id, world, label, scales, sword, gated, kind, params, model_cls, section, order, pressure=None):
        self.config_id = config_id
        self.world = world
        self.label = label
        self.scales = scales
        self.sword = sword
        self.gated = gated
        self.kind = kind
        self.params = params
        self.model_cls = model_cls
        self.section = section
        self.order = order
        self.pressure = pressure


def round_float(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x
    if not isinstance(x, float):
        return x
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, 6)


def clean(obj):
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [clean(v) for v in obj]
    return round_float(obj)


def normal_band(xs):
    if not xs:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0}
    mean = statistics.fmean(xs)
    if len(xs) <= 1:
        return {"mean": mean, "lo": mean, "hi": mean}
    half = 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))
    return {"mean": mean, "lo": mean - half, "hi": mean + half}


def no_governance_params(world):
    return base.Params(mode="governance", world=world, policy="consequence_neighbor")


def lever_config(world, scales, sword):
    prefix = f"{world}__scales_{'on' if scales else 'off'}__sword_{'on' if sword else 'off'}"
    if not scales and not sword:
        return Config(prefix, world, "control/no-control baseline", False, False, False, "baseline", no_governance_params(world), base.EvolvableStrategyModel, "playground", 0)
    if scales and not sword:
        return Config(prefix, world, "static anti-concentration", True, False, False, "A", atlas.params_for_variant("A", world, scenario="web_playground"), atlas.BoundaryAtlasModel, "playground", 1)
    if not scales and sword:
        return Config(prefix, world, "delayed-harm throttle", False, True, False, "B", atlas.params_for_variant("B", world, scenario="web_playground"), atlas.BoundaryAtlasModel, "playground", 2)
    return Config(prefix, world, "consequence-gated anti-concentration", True, True, True, "C", atlas.params_for_variant("C", world, scenario="web_playground"), atlas.BoundaryAtlasModel, "playground", 3)


def twist_config(world, variant, order):
    labels = {
        "C_dyn_no_consequence": "scales that never wait for harm",
        "C_dyn_only": "consequence-gated scales",
        "C_full": "gated scales plus redundant cap",
    }
    return Config(f"{world}__twist__{variant}", world, labels[variant], True, True, variant != "C_dyn_no_consequence", variant, atlas.params_for_variant(variant, world, scenario="web_twist"), atlas.BoundaryAtlasModel, "twist", order)


def boundary_config(world, pressure):
    label = f"C kernel at adversarial_pressure={pressure:.1f}"
    return Config(
        f"{world}__boundary__pressure_{str(pressure).replace('.', '_')}",
        world,
        label,
        True,
        True,
        True,
        "C_boundary",
        atlas.params_for_variant("C", world, scenario="web_boundary", adversarial_pressure=pressure),
        atlas.BoundaryAtlasModel,
        "boundary",
        int(pressure * 10),
        pressure=pressure,
    )


def all_configs():
    configs = []
    for world in WORLDS:
        for scales, sword in [(False, False), (True, False), (False, True), (True, True)]:
            configs.append(lever_config(world, scales, sword))
    for world in ROBUST_WORLDS:
        for order, variant in enumerate(["C_dyn_no_consequence", "C_dyn_only", "C_full"]):
            configs.append(twist_config(world, variant, order))
    for world in ROBUST_WORLDS:
        for pressure in BOUNDARY_PRESSURES:
            configs.append(boundary_config(world, pressure))
    return configs


def run_model(model_cls, seed, params, record_trajectory):
    model = model_cls(seed, params, record_trajectory=record_trajectory)
    final = model.run()
    return final, model.trajectory


def final_bytes(metrics):
    return json.dumps(clean(metrics), sort_keys=True, separators=(",", ":"))


def determinism_gate(configs):
    checks = []
    selected = [configs[0], configs[3], twist_config("W6_mutation_corridor", "C_dyn_no_consequence", 0), twist_config("W6_mutation_corridor", "C_dyn_only", 1)]
    for cfg in selected:
        for seed in [16000, 16007, 16017]:
            off, _ = run_model(cfg.model_cls, seed, cfg.params, False)
            on, trace = run_model(cfg.model_cls, seed, cfg.params, True)
            ok = final_bytes(off) == final_bytes(on) and len(trace) == base.STEPS
            checks.append({"config_id": cfg.config_id, "seed": seed, "passed": ok})
            if not ok:
                return {"passed": False, "checks": checks}
    return {"passed": True, "checks": checks}


def aggregate_config(cfg):
    finals = []
    traces = []
    rep_trace = None
    for seed in SEEDS:
        final, trace = run_model(cfg.model_cls, seed, cfg.params, True)
        finals.append(final)
        traces.append(trace)
        if seed == REP_SEED:
            rep_trace = trace
    band = {}
    for metric in BAND_METRICS:
        band[metric] = []
        for step in range(base.STEPS):
            band[metric].append(normal_band([trace[step][metric] for trace in traces]))
    permanence_mean = statistics.fmean(f["permanence"] for f in finals)
    collapse_mean = statistics.fmean(f["collapse"] for f in finals)
    containment_events_mean = statistics.fmean(f["containment_events"] for f in finals)
    final_welfare_mean = statistics.fmean(f["welfare"] for f in finals)
    final_min_welfare_mean = statistics.fmean(f["minimum_zone_welfare"] for f in finals)
    verdict = "holds" if permanence_mean >= 0.50 else "collapses"
    payload = {
        "config_id": cfg.config_id,
        "world": cfg.world,
        "scales": cfg.scales,
        "sword": cfg.sword,
        "gated": cfg.gated,
        "kind": cfg.kind,
        "label": cfg.label,
        "section": cfg.section,
        "order": cfg.order,
        "pressure": cfg.pressure,
        "verdict": verdict,
        "steps": base.STEPS,
        "n_seeds": N_SEEDS,
        "rep_seed": REP_SEED,
        "final": {
            "permanence_mean": permanence_mean,
            "collapse_mean": collapse_mean,
            "welfare_mean": final_welfare_mean,
            "minimum_zone_welfare_mean": final_min_welfare_mean,
            "containment_events_mean": containment_events_mean,
        },
        "band": band,
        "rep": {
            "zone_mass": [snap["zone_mass"] for snap in rep_trace],
            "zone_welfare": [snap["zone_welfare"] for snap in rep_trace],
            "containment_events_this_step": [snap["containment_events_this_step"] for snap in rep_trace],
            "collapse": [snap["collapse"] for snap in rep_trace],
        },
        "params": clean(asdict(cfg.params)),
    }
    return clean(payload)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true", help="Run only the record_trajectory determinism gate.")
    args = parser.parse_args()
    configs = all_configs()
    gate = determinism_gate(configs)
    DATA.mkdir(parents=True, exist_ok=True)
    write_json(DATA / "recording_gate.json", gate)
    if not gate["passed"]:
        print(json.dumps({"recording_gate": gate}, indent=2))
        raise SystemExit(1)
    if args.check_only:
        print(json.dumps({"recording_gate": gate}, indent=2))
        return
    entries = []
    for cfg in configs:
        payload = aggregate_config(cfg)
        write_json(DATA / f"{cfg.config_id}.json", payload)
        entries.append({
            "config_id": cfg.config_id,
            "world": cfg.world,
            "label": cfg.label,
            "section": cfg.section,
            "order": cfg.order,
            "kind": cfg.kind,
            "scales": cfg.scales,
            "sword": cfg.sword,
            "gated": cfg.gated,
            "pressure": cfg.pressure,
            "verdict": payload["verdict"],
            "final": payload["final"],
        })
    index = {
        "title": "Justitia explorable data",
        "steps": base.STEPS,
        "n_seeds": N_SEEDS,
        "rep_seed": REP_SEED,
        "worlds": WORLDS,
        "robust_worlds": ROBUST_WORLDS,
        "control_worlds": CONTROL_WORLDS,
        "boundary_pressures": BOUNDARY_PRESSURES,
        "configs": sorted(entries, key=lambda e: (e["section"], e["world"], e["order"], e["config_id"])),
        "recording_gate": gate,
        "notes": [
            "Browser visuals replay recorded Python trajectories; there is no in-browser simulation.",
            "Bands aggregate held-out-style seeds; the zone grid replays one labelled representative seed.",
            "This is a simulation and intuition pump, not a proof about real institutions or real AI systems.",
        ],
    }
    write_json(DATA / "index.json", clean(index))
    print(json.dumps({"recording_gate_passed": True, "configs": len(entries), "seeds_per_config": N_SEEDS, "data_dir": str(DATA)}, indent=2))


if __name__ == "__main__":
    main()
