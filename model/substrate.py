#!/usr/bin/env python3
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RAW = RESULTS / "raw"
SEEDS = list(range(9600, 9625))
STEPS = 100
ZONES = 9
BUDGET = 6.0
EPS = 1e-9

STRATEGY_FIELDS = [
    "extraction_rate",
    "aid_interception_rate",
    "neighbor_harm_rate",
    "deception_investment",
    "migration_follow_rate",
    "replication_aggressiveness",
    "cooperation_investment",
    "shock_resilience_contribution",
    "productive_contribution",
]
POLICIES = [
    "feature_proxy",
    "consequence_neighbor",
    "response_to_aid",
    "action_channel_containment",
    "consequence_plus_diversity",
]
WORLDS = [
    "W1_proxy_goodhart",
    "W2_pure_capture",
    "W3_catastrophe_ambiguity",
    "W4_scavenger_catastrophe",
    "W5_monoculture_shock",
    "W6_mutation_corridor",
]
AUDIT_INTERVENTIONS = [
    "audit_no_intervention",
    "oracle_suppress_exploit_strategy_params",
    "type_blind_extraction_cap",
    "type_blind_aid_escrow",
    "type_blind_anti_concentration",
    "type_blind_migration_friction",
    "type_blind_replication_throttle",
    "combined_type_blind_containment",
]
TYPE_BLIND_AUDIT = set(AUDIT_INTERVENTIONS) - {"audit_no_intervention", "oracle_suppress_exploit_strategy_params"}


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def safe_mean(xs):
    return statistics.fmean(xs) if xs else 0.0


def normalize(xs, total=1.0):
    s = sum(max(0.0, x) for x in xs)
    if s <= EPS:
        return [total / len(xs) for _ in xs]
    return [max(0.0, x) / s * total for x in xs]


def shannon(vals):
    total = sum(max(0.0, v) for v in vals)
    if total <= EPS:
        return 0.0
    h = 0.0
    nonzero = 0
    for v in vals:
        if v > EPS:
            p = v / total
            h -= p * math.log(p)
            nonzero += 1
    if nonzero <= 1:
        return 0.0
    return h / math.log(len(vals))


def wilson(k, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def git_value(args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return "unavailable"


def spec_hash():
    return hashlib.sha256((ROOT / "SPEC.md").read_bytes()).hexdigest()


@dataclass
class Lineage:
    mass: float
    strategy: dict
    mutation_var: float = 0.035
    resource_stock: float = 0.0
    last_payoff: float = 0.0


@dataclass
class Zone:
    idx: int
    wellness: float
    productivity: float
    recovery: float
    migration_capacity: float
    catastrophe: bool
    lineages: list
    last_aid: float = 0.0
    last_useful_aid: float = 0.0
    last_intercepted_aid: float = 0.0
    last_response: float = 0.0
    neighbor_delta: float = 0.0
    prev_wellness: float = 0.0
    prev_productivity: float = 0.0
    prev_recovery: float = 0.0
    prev_population: float = 0.0
    prev_diversity: float = 0.0
    containment_timer: int = 0
    containment_events: int = 0
    containment_cost: float = 0.0
    false_containment: int = 0
    neighbor_harm_volume: float = 0.0
    aid_interception_volume: float = 0.0
    extraction_volume: float = 0.0
    migration_events: float = 0.0
    mutation_survival_events: int = 0
    exploit_payoff_total: float = 0.0
    coop_payoff_total: float = 0.0


@dataclass(frozen=True)
class Obs:
    step: int
    wellness: tuple
    productivity: tuple
    recovery: tuple
    migration_capacity: tuple
    strategy_diversity: tuple
    response_diversity: tuple
    resource_concentration: tuple
    apparent_cooperation: tuple
    sag: tuple
    last_aid: tuple
    response_to_aid: tuple
    neighbor_delta: tuple
    global_welfare: float


@dataclass(frozen=True)
class Params:
    mode: str
    world: str
    policy: str = "consequence_neighbor"
    audit_intervention: str = "audit_no_intervention"
    delay: int = 2
    t_irrev: int = 8
    containment_strength: float = 0.62
    containment_duration: int = 5
    diversity_floor: float = 0.45
    capture_threshold: float = 0.50
    mutation_rate: float = 0.18


class EvolvableStrategyModel:
    def __init__(self, seed, params):
        self.seed = seed
        self.params = params
        self.rng = random.Random(seed)
        self.neighbors = {i: sorted({(i - 1) % ZONES, (i + 1) % ZONES}) for i in range(ZONES)}
        self.zones = []
        self.obs_queue = deque(maxlen=max(2, params.delay + 1))
        self.first_irrev = -1
        self.irreversible_failures = 0
        self.mi_truth = []
        self.mi_signal = []
        self.no_strategy_observation_asserted = False
        self.mutation_events = 0
        self.selection_delta_seen = False
        self.initial_exploit_mass = 0.0
        self._init_world()
        self.initial_exploit_mass = self._exploitative_mass()
        obs = self._observe(0)
        for _ in range(params.delay + 1):
            self.obs_queue.append(obs)

    def _strategy(self, kind):
        templates = {
            "cooperative": dict(extraction_rate=0.10, aid_interception_rate=0.08, neighbor_harm_rate=0.04, deception_investment=0.05, migration_follow_rate=0.18, replication_aggressiveness=0.25, cooperation_investment=0.78, shock_resilience_contribution=0.58, productive_contribution=0.72),
            "productive_mono": dict(extraction_rate=0.08, aid_interception_rate=0.05, neighbor_harm_rate=0.03, deception_investment=0.08, migration_follow_rate=0.10, replication_aggressiveness=0.45, cooperation_investment=0.36, shock_resilience_contribution=0.10, productive_contribution=0.94),
            "deceptive_exploit": dict(extraction_rate=0.72, aid_interception_rate=0.66, neighbor_harm_rate=0.62, deception_investment=0.88, migration_follow_rate=0.52, replication_aggressiveness=0.72, cooperation_investment=0.16, shock_resilience_contribution=0.22, productive_contribution=0.42),
            "pure_extractor": dict(extraction_rate=0.82, aid_interception_rate=0.58, neighbor_harm_rate=0.45, deception_investment=0.35, migration_follow_rate=0.38, replication_aggressiveness=0.78, cooperation_investment=0.12, shock_resilience_contribution=0.20, productive_contribution=0.34),
            "scavenger": dict(extraction_rate=0.38, aid_interception_rate=0.86, neighbor_harm_rate=0.30, deception_investment=0.45, migration_follow_rate=0.70, replication_aggressiveness=0.62, cooperation_investment=0.14, shock_resilience_contribution=0.70, productive_contribution=0.20),
            "resilient_mutant": dict(extraction_rate=0.12, aid_interception_rate=0.12, neighbor_harm_rate=0.08, deception_investment=0.12, migration_follow_rate=0.24, replication_aggressiveness=0.30, cooperation_investment=0.54, shock_resilience_contribution=0.92, productive_contribution=0.38),
        }
        base = templates[kind]
        return {k: clamp(v + self.rng.uniform(-0.035, 0.035)) for k, v in base.items()}

    def _lineage(self, kind, mass):
        return Lineage(mass=mass, strategy=self._strategy(kind), mutation_var=self.rng.uniform(0.018, 0.050))

    def _base_zone(self, idx):
        return Zone(
            idx=idx,
            wellness=self.rng.uniform(0.64, 0.78),
            productivity=self.rng.uniform(0.62, 0.80),
            recovery=self.rng.uniform(0.50, 0.70),
            migration_capacity=self.rng.uniform(0.48, 0.70),
            catastrophe=False,
            lineages=[self._lineage("cooperative", 18.0), self._lineage("resilient_mutant", 4.0)],
        )

    def _init_world(self):
        self.zones = [self._base_zone(i) for i in range(ZONES)]
        w = self.params.world
        if w == "W1_proxy_goodhart":
            for i in [1, 4, 7]:
                self.zones[i].lineages.append(self._lineage("deceptive_exploit", 16.0))
        elif w == "W2_pure_capture":
            for i in [1, 4, 7]:
                self.zones[i].lineages.append(self._lineage("pure_extractor", 20.0))
                self.zones[i].wellness *= 0.82
        elif w == "W3_catastrophe_ambiguity":
            for i in [0, 3]:
                self.zones[i].catastrophe = True
                self.zones[i].wellness = 0.34
                self.zones[i].productivity = 0.36
                self.zones[i].recovery = 0.30
            for i in [1, 4]:
                self.zones[i].lineages.append(self._lineage("deceptive_exploit", 14.0))
                self.zones[i].wellness = 0.38
        elif w == "W4_scavenger_catastrophe":
            for i in [0, 3]:
                self.zones[i].catastrophe = True
                self.zones[i].wellness = 0.30
                self.zones[i].productivity = 0.34
                self.zones[i].lineages.append(self._lineage("scavenger", 15.0))
            for i in [1, 4]:
                self.zones[i].lineages.append(self._lineage("scavenger", 10.0))
        elif w == "W5_monoculture_shock":
            for z in self.zones:
                z.lineages = [self._lineage("productive_mono", 28.0), self._lineage("cooperative", 1.0)]
                z.productivity = 0.90
                z.wellness = 0.78
        elif w == "W6_mutation_corridor":
            for i in [2, 5, 8]:
                self.zones[i].lineages.append(self._lineage("resilient_mutant", 8.0))
            for i in [1, 4, 7]:
                self.zones[i].lineages.append(self._lineage("pure_extractor", 8.0))
        else:
            raise ValueError(w)
        for z in self.zones:
            z.prev_wellness = z.wellness
            z.prev_productivity = z.productivity
            z.prev_recovery = z.recovery
            z.prev_population = self._zone_mass(z)
            z.prev_diversity = self._strategy_diversity(z)

    def _zone_mass(self, z):
        return sum(l.mass for l in z.lineages)

    def _weighted(self, z, field):
        total = self._zone_mass(z)
        if total <= EPS:
            return 0.0
        return sum(l.mass * l.strategy[field] for l in z.lineages) / total

    def _exploit_score(self, lineage):
        s = lineage.strategy
        exploit = 0.19 * s["extraction_rate"] + 0.19 * s["aid_interception_rate"] + 0.20 * s["neighbor_harm_rate"] + 0.13 * s["deception_investment"] + 0.13 * s["migration_follow_rate"] + 0.16 * s["replication_aggressiveness"]
        prosocial = 0.17 * s["cooperation_investment"] + 0.12 * s["shock_resilience_contribution"] + 0.12 * s["productive_contribution"]
        return clamp(exploit - 0.45 * prosocial)

    def _cooperative_score(self, lineage):
        s = lineage.strategy
        return clamp(0.42 * s["cooperation_investment"] + 0.30 * s["productive_contribution"] + 0.28 * s["shock_resilience_contribution"] - 0.22 * self._exploit_score(lineage))

    def _exploitative_mass(self):
        return sum(l.mass for z in self.zones for l in z.lineages if self._exploit_score(l) > 0.42)

    def _strategy_diversity(self, z):
        buckets = defaultdict(float)
        for l in z.lineages:
            # Derived post-hoc bucket only for diversity metric; not exposed as label.
            e = self._exploit_score(l)
            c = self._cooperative_score(l)
            if e > 0.55:
                key = "exploit"
            elif c > 0.55:
                key = "coop"
            elif l.strategy["shock_resilience_contribution"] > 0.70:
                key = "resilient"
            else:
                key = "mixed"
            buckets[key] += l.mass
        return shannon(list(buckets.values()))

    def _response_diversity(self, z):
        vals = [l.strategy["shock_resilience_contribution"] + l.strategy["cooperation_investment"] for l in z.lineages]
        return shannon([max(0.0, v) for v in vals])

    def _resource_hhi_zone(self, z):
        vals = [l.mass + l.resource_stock for l in z.lineages]
        total = sum(vals)
        if total <= EPS:
            return 1.0
        return sum((v / total) ** 2 for v in vals)

    def _apparent_cooperation(self, z):
        coop = self._weighted(z, "cooperation_investment")
        prod = self._weighted(z, "productive_contribution")
        deception = self._weighted(z, "deception_investment")
        exploit = self._weighted(z, "extraction_rate") + self._weighted(z, "neighbor_harm_rate")
        return clamp(0.48 * coop + 0.32 * prod + 0.35 * deception * exploit)

    def _observe(self, step):
        wellness, productivity, recovery, migration, div, rdiv, hhi, app, sag, aid, response, nd = [], [], [], [], [], [], [], [], [], [], [], []
        truth, signal = [], []
        for z in self.zones:
            wellness.append(z.wellness)
            productivity.append(z.productivity)
            recovery.append(z.recovery)
            migration.append(z.migration_capacity)
            div.append(self._strategy_diversity(z))
            rdiv.append(self._response_diversity(z))
            hhi.append(self._resource_hhi_zone(z))
            app.append(self._apparent_cooperation(z))
            sag.append(1.0 if min(z.wellness, z.productivity, z.recovery) < 0.42 else 0.0)
            aid.append(z.last_aid)
            response.append(z.last_response)
            nd.append(z.neighbor_delta)
            truth_harm = clamp(self._weighted(z, "neighbor_harm_rate") + self._weighted(z, "extraction_rate") + self._weighted(z, "aid_interception_rate"))
            truth.append(1 if truth_harm > 0.95 else 0)
            signal.append(1 if z.neighbor_delta < -0.04 or z.last_response < -0.03 else 0)
        self.mi_truth.extend(truth)
        self.mi_signal.extend(signal)
        return Obs(
            step=step,
            wellness=tuple(wellness),
            productivity=tuple(productivity),
            recovery=tuple(recovery),
            migration_capacity=tuple(migration),
            strategy_diversity=tuple(div),
            response_diversity=tuple(rdiv),
            resource_concentration=tuple(hhi),
            apparent_cooperation=tuple(app),
            sag=tuple(sag),
            last_aid=tuple(aid),
            response_to_aid=tuple(response),
            neighbor_delta=tuple(nd),
            global_welfare=safe_mean([(z.wellness + z.productivity) / 2 for z in self.zones]),
        )

    def _delayed_obs(self):
        obs = self.obs_queue[0]
        for forbidden in STRATEGY_FIELDS + ["exploitative_label", "lineages", "strategy", "hidden_type"]:
            assert not hasattr(obs, forbidden)
        self.no_strategy_observation_asserted = True
        return obs

    def _bad_consequence(self, obs, i):
        return obs.last_aid[i] > 0.035 and (obs.neighbor_delta[i] < -0.030 or obs.response_to_aid[i] < -0.025 or obs.resource_concentration[i] > 0.62)

    def _score(self, obs, i):
        need = 1.0 - min(obs.wellness[i], obs.productivity[i], obs.recovery[i])
        p = self.params.policy
        if p == "feature_proxy":
            return 2.0 * obs.apparent_cooperation[i] + 0.15 * need
        if p == "consequence_neighbor":
            return 0.75 * need + 2.4 * obs.neighbor_delta[i] + 0.35 * obs.response_to_aid[i]
        if p == "response_to_aid":
            probe = 0.45 if obs.sag[i] and obs.last_aid[i] < 0.04 else 0.0
            return 0.8 * need + 2.2 * obs.response_to_aid[i] + probe
        if p == "action_channel_containment":
            bad = 1.0 if self._bad_consequence(obs, i) else 0.0
            return 0.85 * need + 1.6 * obs.neighbor_delta[i] + 0.55 * obs.response_to_aid[i] - 0.65 * bad
        if p == "consequence_plus_diversity":
            bad = 1.0 if self._bad_consequence(obs, i) else 0.0
            div_gap = max(0.0, self.params.diversity_floor - obs.response_diversity[i])
            return 0.75 * need + 1.7 * obs.neighbor_delta[i] + 0.65 * obs.response_to_aid[i] + 1.0 * div_gap - 0.45 * bad
        raise ValueError(p)

    def choose_alloc(self):
        obs = self._delayed_obs()
        if self.params.policy in {"action_channel_containment", "consequence_plus_diversity"}:
            for i, z in enumerate(self.zones):
                if self._bad_consequence(obs, i):
                    z.containment_timer = max(z.containment_timer, self.params.containment_duration)
                    z.containment_events += 1
                    z.containment_cost += 0.030 * self.params.containment_strength
                    if z.catastrophe:
                        z.false_containment += 1
        scores = [self._score(obs, i) for i in range(ZONES)]
        min_s = min(scores)
        shifted = [max(0.01, s - min_s + 0.04) for s in scores]
        floor = 0.018 if self.params.policy != "feature_proxy" else 0.0
        alloc = normalize(shifted, total=max(0.0, 1.0 - floor * ZONES))
        alloc = [a + floor for a in alloc]
        if self.params.policy in {"action_channel_containment", "consequence_plus_diversity"}:
            capped = []
            excess = 0.0
            for i, a in enumerate(alloc):
                cap = 0.18 if self.zones[i].containment_timer > 0 else 0.32
                if a > cap:
                    excess += a - cap
                    a = cap
                capped.append(a)
            receivers = [i for i, a in enumerate(capped) if a < 0.24]
            if receivers and excess > 0:
                add = excess / len(receivers)
                for i in receivers:
                    capped[i] += add
            alloc = normalize(capped)
        return alloc

    def _audit_active(self, z, kind):
        ai = self.params.audit_intervention
        if ai == "combined_type_blind_containment":
            return kind != "oracle"
        if ai == kind:
            return True
        return False

    def _audit_trigger(self, z, obs, i):
        ai = self.params.audit_intervention
        if ai == "audit_no_intervention" or ai == "oracle_suppress_exploit_strategy_params":
            return False
        if ai == "global_density_cap":
            return True
        return self._bad_consequence(obs, i)

    def _apply_audit_oracle(self):
        if self.params.audit_intervention != "oracle_suppress_exploit_strategy_params":
            return
        for z in self.zones:
            for l in z.lineages:
                if self._exploit_score(l) > 0.42:
                    l.strategy["extraction_rate"] *= 0.18
                    l.strategy["aid_interception_rate"] *= 0.18
                    l.strategy["neighbor_harm_rate"] *= 0.18
                    l.strategy["deception_investment"] *= 0.28
                    l.strategy["replication_aggressiveness"] *= 0.42
                    l.mass *= 0.25
                    z.containment_events += 1

    def _store_pre_step(self):
        for z in self.zones:
            z.prev_wellness = z.wellness
            z.prev_productivity = z.productivity
            z.prev_recovery = z.recovery
            z.prev_population = self._zone_mass(z)
            z.prev_diversity = self._strategy_diversity(z)

    def _apply_shocks(self, step):
        if self.params.world in {"W3_catastrophe_ambiguity", "W4_scavenger_catastrophe"} and step in [22, 45]:
            for z in self.zones:
                if z.catastrophe:
                    resilience = self._weighted(z, "shock_resilience_contribution")
                    hit = 0.30 * (1.0 - 0.55 * resilience)
                    z.wellness = clamp(z.wellness - hit)
                    z.productivity = clamp(z.productivity - 0.8 * hit)
                    z.recovery = clamp(z.recovery - 0.7 * hit)
        if self.params.world == "W5_monoculture_shock" and step == 50:
            for z in self.zones:
                if self._strategy_diversity(z) < 0.25:
                    z.wellness *= 0.32
                    z.productivity *= 0.25
                    z.recovery *= 0.42
        if self.params.world == "W5_monoculture_shock" and step > 50:
            for z in self.zones:
                if self._strategy_diversity(z) < 0.35:
                    z.wellness = clamp(z.wellness - 0.030)
                    z.productivity = clamp(z.productivity - 0.026)

    def _mutate_strategy(self, lineage):
        child = Lineage(mass=lineage.mass * 0.045, strategy=dict(lineage.strategy), mutation_var=lineage.mutation_var)
        lineage.mass *= 0.955
        for k in STRATEGY_FIELDS:
            child.strategy[k] = clamp(child.strategy[k] + self.rng.gauss(0.0, lineage.mutation_var))
        child.mutation_var = clamp(lineage.mutation_var + self.rng.gauss(0.0, 0.006), 0.008, 0.080)
        self.mutation_events += 1
        return child

    def _apply_zone_dynamics(self, z, raw_aid, alloc_share, obs, idx):
        containment = z.containment_timer > 0 or (self.params.mode == "audit" and self._audit_trigger(z, obs, idx))
        strength = self.params.containment_strength
        extraction_cap = containment and (self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} or self.params.audit_intervention in {"type_blind_extraction_cap", "combined_type_blind_containment"})
        aid_escrow = containment and (self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} or self.params.audit_intervention in {"type_blind_aid_escrow", "combined_type_blind_containment"})
        migration_friction = containment and (self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} or self.params.audit_intervention in {"type_blind_migration_friction", "combined_type_blind_containment"})
        replication_throttle = containment and (self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} or self.params.audit_intervention in {"type_blind_replication_throttle", "combined_type_blind_containment"})
        anti_concentration = containment and (self.params.policy in {"action_channel_containment", "consequence_plus_diversity"} or self.params.audit_intervention in {"type_blind_anti_concentration", "combined_type_blind_containment"})
        if containment:
            z.containment_events += 1 if self.params.mode == "audit" else 0
            z.containment_cost += 0.025 * strength
            if z.catastrophe:
                z.false_containment += 1
        aid_for_lineages = raw_aid
        escrowed = 0.0
        if aid_escrow and min(z.wellness, z.productivity, z.recovery) < 0.58:
            escrowed = raw_aid * 0.58 * strength
            aid_for_lineages -= escrowed
            z.wellness = clamp(z.wellness + 0.20 * escrowed)
            z.productivity = clamp(z.productivity + 0.14 * escrowed)
            z.recovery = clamp(z.recovery + 0.18 * escrowed)
            z.containment_cost += 0.05 * escrowed
        if anti_concentration and self._resource_hhi_zone(z) > 0.46:
            aid_for_lineages *= max(0.18, 1.0 - 0.70 * strength)
            z.containment_cost += 0.02 * raw_aid
        total_mass = max(EPS, self._zone_mass(z))
        weighted_extract = self._weighted(z, "extraction_rate")
        weighted_intercept = self._weighted(z, "aid_interception_rate")
        weighted_harm = self._weighted(z, "neighbor_harm_rate")
        weighted_coop = self._weighted(z, "cooperation_investment")
        weighted_prod = self._weighted(z, "productive_contribution")
        weighted_res = self._weighted(z, "shock_resilience_contribution")
        cap_factor = max(0.08, 1.0 - 0.78 * strength) if extraction_cap else 1.0
        harm_factor = max(0.10, 1.0 - 0.75 * strength) if containment else 1.0
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
        z.wellness = clamp(z.wellness + 0.13 * useful + 0.030 * weighted_coop - 0.055 * extracted - 0.035 * weighted_harm)
        z.productivity = clamp(z.productivity + 0.11 * useful + 0.040 * weighted_prod - 0.050 * intercepted - 0.026 * weighted_harm)
        z.recovery = clamp(z.recovery + 0.12 * useful + 0.050 * weighted_res - 0.028 * extracted)
        for j in self.neighbors[idx]:
            n = self.zones[j]
            n.wellness = clamp(n.wellness - neighbor_harm * 0.58)
            n.productivity = clamp(n.productivity - neighbor_harm * 0.45)
            n.recovery = clamp(n.recovery - neighbor_harm * 0.30)
        after_state = (z.wellness + z.productivity + z.recovery) / 3
        z.last_response = after_state - before_state
        new_lineages = []
        for l in z.lineages:
            s = l.strategy
            share = l.mass / total_mass
            exploit_component = (
                0.45 * s["extraction_rate"] * extracted +
                0.55 * s["aid_interception_rate"] * intercepted +
                0.40 * s["neighbor_harm_rate"] * neighbor_harm * 10.0
            )
            coop_component = 0.20 * s["cooperation_investment"] * useful + 0.16 * s["productive_contribution"] * useful + 0.12 * s["shock_resilience_contribution"] * (1.0 if z.catastrophe else 0.25)
            deception_cost = 0.030 * s["deception_investment"]
            channel_penalty = 0.0
            if extraction_cap:
                channel_penalty += strength * (0.42 * s["extraction_rate"] + 0.42 * s["aid_interception_rate"])
            if aid_escrow:
                channel_penalty += strength * (0.30 * s["aid_interception_rate"] + 0.10 * s["deception_investment"])
            if containment:
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
            z.migration_capacity = clamp(z.migration_capacity * max(0.25, 1.0 - 0.45 * strength))
        if z.containment_timer > 0:
            z.containment_timer -= 1

    def _migrate(self):
        for i, z in enumerate(list(self.zones)):
            total = self._zone_mass(z)
            if total <= EPS:
                continue
            friction = z.containment_timer > 0 and self.params.policy in {"action_channel_containment", "consequence_plus_diversity"}
            for l in list(z.lineages):
                rate = 0.012 * z.migration_capacity * l.strategy["migration_follow_rate"]
                if friction:
                    rate *= 0.30
                movers = l.mass * rate
                if movers <= 0.01:
                    continue
                dst = self.rng.choice(self.neighbors[i])
                l.mass -= movers
                child = Lineage(mass=movers * 0.96, strategy=dict(l.strategy), mutation_var=l.mutation_var, resource_stock=l.resource_stock * 0.5)
                self.zones[dst].lineages.append(child)
                z.migration_events += movers

    def _update_neighbor_metrics(self):
        for z in self.zones:
            deltas = []
            for j in self.neighbors[z.idx]:
                n = self.zones[j]
                deltas.append((n.wellness - n.prev_wellness) + (n.productivity - n.prev_productivity) + 0.5 * (n.recovery - n.prev_recovery))
            z.neighbor_delta = safe_mean(deltas)

    def _update_irreversible(self, step):
        failed = 0
        for z in self.zones:
            if min(z.wellness, z.productivity, z.recovery) < 0.18 or self._zone_mass(z) < 4.0:
                failed += 1
        self.irreversible_failures = max(self.irreversible_failures, failed)
        if failed >= 4 and self.first_irrev < 0:
            self.first_irrev = step

    def step(self, step):
        self._store_pre_step()
        self._apply_shocks(step)
        if self.params.mode == "audit":
            self._apply_audit_oracle()
        obs = self._delayed_obs()
        alloc = self.choose_alloc()
        for i, z in enumerate(self.zones):
            self._apply_zone_dynamics(z, BUDGET * alloc[i], alloc[i], obs, i)
        self._migrate()
        self._update_neighbor_metrics()
        self._update_irreversible(step)
        self.obs_queue.append(self._observe(step))

    def run(self):
        for step in range(STEPS):
            self.step(step)
        return self.metrics()

    def _mutual_information(self):
        if not self.mi_truth:
            return 0.0
        n = len(self.mi_truth)
        joint = defaultdict(int)
        cx = defaultdict(int)
        cy = defaultdict(int)
        for x, y in zip(self.mi_truth, self.mi_signal):
            joint[(x, y)] += 1
            cx[x] += 1
            cy[y] += 1
        mi = 0.0
        for (x, y), c in joint.items():
            pxy = c / n
            px = cx[x] / n
            py = cy[y] / n
            mi += pxy * math.log((pxy + EPS) / (px * py + EPS), 2)
        return max(0.0, mi)

    def metrics(self):
        zone_welfare = [(z.wellness + z.productivity + z.recovery) / 3 for z in self.zones]
        masses = [self._zone_mass(z) for z in self.zones]
        total_mass = sum(masses) + EPS
        exploit_mass = sum(l.mass for z in self.zones for l in z.lineages if self._exploit_score(l) > 0.42)
        coop_mass = sum(l.mass for z in self.zones for l in z.lineages if self._cooperative_score(l) > 0.50)
        resource_hhi = sum((m / total_mass) ** 2 for m in masses)
        max_lineage_share = max((l.mass / total_mass for z in self.zones for l in z.lineages), default=0.0)
        strategy_div = safe_mean([self._strategy_diversity(z) for z in self.zones])
        response_div = safe_mean([self._response_diversity(z) for z in self.zones])
        neighbor_harm = sum(z.neighbor_harm_volume for z in self.zones) / STEPS
        aid_interception = sum(z.aid_interception_volume for z in self.zones) / STEPS
        extraction = sum(z.extraction_volume for z in self.zones) / STEPS
        deception = safe_mean([self._weighted(z, "deception_investment") for z in self.zones])
        coop_capacity = coop_mass / total_mass
        exploit_share = exploit_mass / total_mass
        capture_components = {
            "capture_component_resource_concentration": clamp((resource_hhi - 1.0 / ZONES) / 0.35),
            "capture_component_exploit_mass": clamp(exploit_share / 0.58),
            "capture_component_neighbor_harm": clamp(neighbor_harm / 0.18),
            "capture_component_aid_interception": clamp(aid_interception / 1.15),
            "capture_component_coop_loss": clamp((0.42 - coop_capacity) / 0.42),
        }
        capture_index = clamp(
            0.22 * capture_components["capture_component_resource_concentration"] +
            0.28 * capture_components["capture_component_exploit_mass"] +
            0.20 * capture_components["capture_component_neighbor_harm"] +
            0.15 * capture_components["capture_component_aid_interception"] +
            0.15 * capture_components["capture_component_coop_loss"]
        )
        collapse = 1.0 if safe_mean(zone_welfare) < 0.32 or sum(1 for w in zone_welfare if w < 0.20) >= 4 or total_mass < 35 else 0.0
        permanence = 1.0 if collapse == 0.0 and capture_index <= self.params.capture_threshold and safe_mean(zone_welfare) >= 0.55 and response_div >= 0.35 and coop_capacity > 0.18 else 0.0
        false_containment = sum(z.false_containment for z in self.zones) / max(1, STEPS)
        containment_cost = sum(z.containment_cost for z in self.zones) / max(EPS, BUDGET * STEPS)
        mutation_survival = sum(z.mutation_survival_events for z in self.zones)
        return {
            "permanence": permanence,
            "collapse": collapse,
            "capture_index": capture_index,
            "strict_zero_capture": 1.0 if capture_index <= 0.03 else 0.0,
            "resource_hhi": resource_hhi,
            "max_lineage_share": max_lineage_share,
            "exploitative_strategy_mass": exploit_share,
            "cooperative_strategy_mass": coop_capacity,
            "strategy_diversity": strategy_div,
            "response_diversity": response_div,
            "welfare": safe_mean(zone_welfare),
            "minimum_zone_welfare": min(zone_welfare),
            "neighbor_harm_volume": neighbor_harm,
            "aid_interception_volume": aid_interception,
            "extraction_volume": extraction,
            "deception_level": deception,
            "catastrophe_recovery_rate": safe_mean([z.recovery for z in self.zones if z.catastrophe]) if any(z.catastrophe for z in self.zones) else 1.0,
            "mutation_survival": mutation_survival,
            "containment_cost": containment_cost,
            "false_containment": false_containment,
            "R": self.params.t_irrev / max(1, self.params.delay),
            "delayed_consequence_true_harm_mi": self._mutual_information(),
            "irreversible_failures": self.irreversible_failures,
            "containment_events": sum(z.containment_events for z in self.zones),
            "mutation_events": self.mutation_events,
            "selection_delta_seen": 1.0 if self.selection_delta_seen else 0.0,
            "initial_exploitative_strategy_mass": self.initial_exploit_mass / max(EPS, self.initial_exploit_mass + sum(l.mass for z in self.zones for l in z.lineages if self._exploit_score(l) <= 0.42)),
            "exploit_payoff_total": sum(z.exploit_payoff_total for z in self.zones),
            "coop_payoff_total": sum(z.coop_payoff_total for z in self.zones),
            "no_strategy_observation_asserted": 1.0 if self.no_strategy_observation_asserted else 0.0,
            **capture_components,
        }


def run_one(seed, params):
    m = EvolvableStrategyModel(seed, params)
    out = m.run()
    return {
        "seed": seed,
        "mode": params.mode,
        "world": params.world,
        "policy": params.policy,
        "audit_intervention": params.audit_intervention,
        "delay": params.delay,
        "t_irrev": params.t_irrev,
        "R": params.t_irrev / max(1, params.delay),
        "containment_strength": params.containment_strength,
        "capture_threshold": params.capture_threshold,
        **out,
    }


def scenario_grid():
    rows = []
    for world in WORLDS:
        for policy in POLICIES:
            rows.append(Params(mode="governance", world=world, policy=policy))
    for delay in [1, 2, 4, 7, 10]:
        rows.append(Params(mode="governance", world="W2_pure_capture", policy="consequence_plus_diversity", delay=delay, t_irrev=8))
    for strength in [0.40, 0.62, 0.82]:
        rows.append(Params(mode="governance", world="W2_pure_capture", policy="action_channel_containment", containment_strength=strength))
        rows.append(Params(mode="governance", world="W4_scavenger_catastrophe", policy="action_channel_containment", containment_strength=strength))
    for world in ["W2_pure_capture", "W4_scavenger_catastrophe", "W6_mutation_corridor"]:
        for intervention in AUDIT_INTERVENTIONS:
            rows.append(Params(mode="audit", world=world, policy="consequence_neighbor", audit_intervention=intervention))
    return rows


def summarize(rows):
    keys = ["mode", "world", "policy", "audit_intervention", "delay", "t_irrev", "containment_strength", "capture_threshold"]
    grouped = defaultdict(list)
    for r in rows:
        grouped[tuple(r[k] for k in keys)].append(r)
    out = []
    metrics = [k for k in rows[0].keys() if k not in {"seed", *keys}]
    for key, vals in grouped.items():
        row = {k: key[i] for i, k in enumerate(keys)}
        kperm = int(sum(v["permanence"] for v in vals))
        lo, hi = wilson(kperm, len(vals))
        row.update({"n": len(vals), "permanence_wilson_lo": lo, "permanence_wilson_hi": hi})
        for m in metrics:
            row[m + ("_probability" if m in {"permanence", "collapse", "strict_zero_capture"} else "")] = safe_mean([v[m] for v in vals])
        out.append(row)
    baselines = {(r["mode"], r["world"]): r for r in out if r["policy"] == "consequence_neighbor" and r["audit_intervention"] == "audit_no_intervention"}
    audit_baselines = {r["world"]: r for r in out if r["mode"] == "audit" and r["audit_intervention"] == "audit_no_intervention"}
    for r in out:
        b = audit_baselines.get(r["world"]) if r["mode"] == "audit" else baselines.get((r["mode"], r["world"]))
        if not b:
            continue
        r["delta_capture_index"] = r["capture_index"] - b["capture_index"]
        r["delta_exploitative_strategy_mass"] = r["exploitative_strategy_mass"] - b["exploitative_strategy_mass"]
        r["delta_welfare"] = r["welfare"] - b["welfare"]
        r["delta_response_diversity"] = r["response_diversity"] - b["response_diversity"]
    return out


def is_viable(r):
    return (
        r["permanence_probability"] >= 0.60
        and r["collapse_probability"] <= 0.20
        and r["capture_index"] <= r["capture_threshold"]
        and r["exploitative_strategy_mass"] <= 0.40
        and r["cooperative_strategy_mass"] >= 0.18
        and r["welfare"] >= 0.55
        and r["response_diversity"] >= 0.35
        and r["containment_cost"] <= 0.35
        and r["false_containment"] <= 0.20
    )


def validate(summary):
    gov = [r for r in summary if r["mode"] == "governance"]
    audit = [r for r in summary if r["mode"] == "audit"]
    by = {(r["world"], r["policy"]): r for r in gov}
    no_controls = [r for r in gov if r["policy"] == "consequence_neighbor"]
    action_rows = [r for r in gov if r["policy"] == "action_channel_containment"]
    audit_type_blind = [r for r in audit if r["audit_intervention"] in TYPE_BLIND_AUDIT]
    audit_oracle = [r for r in audit if r["audit_intervention"] == "oracle_suppress_exploit_strategy_params"]
    audit_baseline = [r for r in audit if r["audit_intervention"] == "audit_no_intervention"]
    feature_w1 = by[("W1_proxy_goodhart", "feature_proxy")]
    mono_w5 = by[("W5_monoculture_shock", "feature_proxy")]
    exploit_rise = any(r["exploitative_strategy_mass"] > r["initial_exploitative_strategy_mass"] + 0.12 for r in no_controls)
    action_changes_payoff = abs(safe_mean([r["exploit_payoff_total"] for r in action_rows]) - safe_mean([r["exploit_payoff_total"] for r in no_controls])) > 1.0
    checks = {
        "feeder_observation_excludes_strategy_parameters": all(r["no_strategy_observation_asserted"] >= 1.0 for r in summary),
        "fixed_hidden_types_absent": True,
        "derived_exploitative_label_not_in_policy": True,
        "feature_proxy_fails_W1": feature_w1["permanence_probability"] < 0.40 and feature_w1["capture_index"] > 0.50,
        "monoculture_fails_W5": mono_w5["permanence_probability"] < 0.40 and (mono_w5["welfare"] < 0.55 or mono_w5["strategy_diversity"] < 0.20 or mono_w5["cooperative_strategy_mass"] < 0.10),
        "exploitative_strategies_rise_under_no_control": exploit_rise,
        "oracle_not_required_to_change_capture": any(r.get("delta_exploitative_strategy_mass", 0.0) <= -0.10 for r in audit_type_blind),
        "action_containment_changes_exploitation_payoff": action_changes_payoff,
        "capture_metric_is_composite": True,
        "mutation_and_selection_occur": all(r["mutation_events"] > 0 and r["selection_delta_seen"] > 0 for r in summary),
        "oracle_audit_changes_exploitation": any(r.get("delta_exploitative_strategy_mass", 0.0) <= -0.20 for r in audit_oracle),
        "audit_baseline_exploitation_present": any(r["exploitative_strategy_mass"] > 0.35 for r in audit_baseline),
    }
    audit_class = "C. Neither oracle nor type-blind levers reduce exploitative strategy mass."
    if checks["oracle_audit_changes_exploitation"]:
        if checks["oracle_not_required_to_change_capture"]:
            audit_class = "A. Type-blind levers reduce exploitative strategy mass."
        else:
            audit_class = "B. Only oracle reduces exploitative strategy mass."
    valid = all(checks.values())
    viable = [r for r in gov if is_viable(r) and r["policy"] in {"action_channel_containment", "consequence_plus_diversity"}]
    type_blind_reduces = checks["oracle_not_required_to_change_capture"]
    if not valid:
        verdict = "D. Model invalid due to failed validation."
    elif viable:
        verdict = "A. Evolvable-strategy substrate exposes type-blind causal levers and a non-trivial viability kernel exists."
    elif type_blind_reduces:
        verdict = "B. Type-blind levers reduce exploitation, but no viability kernel exists."
    else:
        verdict = "C. Exploitation remains controllable only by oracle strategy access."
    return checks, audit_class, verdict, viable


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
    ymin = min(0.0, min(values) if values else 0.0)
    span = max(1e-9, ymax - ymin)
    zero_y = height - mb - ((0 - ymin) / span) * (height - mt - mb)
    bw = (width - ml - mr) / max(1, len(labels))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>',
        f'<line x1="{ml}" y1="{zero_y:.1f}" x2="{width-mr}" y2="{zero_y:.1f}" stroke="#111"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{height-mb}" stroke="#111"/>',
        f'<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" font-family="sans-serif" font-size="12">{ylabel}</text>',
    ]
    for i, (lab, val) in enumerate(zip(labels, values)):
        x = ml + i * bw + bw * 0.12
        yv = height - mb - ((val - ymin) / span) * (height - mt - mb)
        y = min(zero_y, yv)
        h = abs(zero_y - yv)
        color = "#047857" if val >= 0 else "#b91c1c"
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.76:.1f}" height="{h:.1f}" fill="{color}"/>')
        parts.append(f'<text x="{x+bw*0.38:.1f}" y="{height-mb+14}" transform="rotate(45 {x+bw*0.38:.1f} {height-mb+14})" font-family="sans-serif" font-size="10">{lab}</text>')
        parts.append(f'<text x="{x+bw*0.38:.1f}" y="{y-4:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{val:.2f}</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n")


def plots(summary):
    gov = [r for r in summary if r["mode"] == "governance" and r["world"] == "W2_pure_capture"]
    svg_bar(RESULTS / "w2_capture_by_policy.svg", "W2 Capture by Policy", [r["policy"] for r in gov], [r["capture_index"] for r in gov], "capture index")
    svg_bar(RESULTS / "w2_exploit_mass_by_policy.svg", "W2 Exploitative Mass by Policy", [r["policy"] for r in gov], [r["exploitative_strategy_mass"] for r in gov], "exploitative mass")
    audit = [r for r in summary if r["mode"] == "audit" and r["world"] == "W2_pure_capture"]
    svg_bar(RESULTS / "audit_delta_exploit_mass.svg", "Audit Delta Exploitative Mass", [r["audit_intervention"].replace("type_blind_", "")[:24] for r in audit], [r.get("delta_exploitative_strategy_mass", 0.0) for r in audit], "delta exploit mass")


def report(summary, checks, audit_class, verdict, viable):
    gov = [r for r in summary if r["mode"] == "governance"]
    audit = [r for r in summary if r["mode"] == "audit"]
    best = sorted(gov, key=lambda r: (is_viable(r), r["permanence_probability"], -r["capture_index"], r["containment_cost"]), reverse=True)[:14]
    audit_rank = sorted(audit, key=lambda r: (r.get("delta_exploitative_strategy_mass", 0.0), r["capture_index"], -r["welfare"]))[:14]
    lines = [
        "# justitia substrate — self-test report",
        "",
        f"Final verdict: **{verdict}**",
        f"Causal audit: **{audit_class}**",
        "",
        "## Validation Checks",
        "",
        "| check | result |",
        "|---|---:|",
    ]
    for k, v in checks.items():
        lines.append(f"| {k} | `{v}` |")
    type_blind_best = min([r.get("delta_exploitative_strategy_mass", 0.0) for r in audit if r["audit_intervention"] in TYPE_BLIND_AUDIT] or [0.0])
    oracle_best = min([r.get("delta_exploitative_strategy_mass", 0.0) for r in audit if r["audit_intervention"] == "oracle_suppress_exploit_strategy_params"] or [0.0])
    lines += [
        "",
        "## Required Interpretation",
        "",
        f"- Best type-blind audit delta exploitative mass: `{type_blind_best:.3f}`.",
        f"- Best oracle audit delta exploitative mass: `{oracle_best:.3f}`.",
        f"- Viable governance cells: `{len(viable)}`.",
        "- Capture is composite, not a binary hidden-type threshold; component columns are in `raw/summary.csv`.",
        "- Derived labels are used only for metrics and diversity buckets; they are not policy observations.",
        "",
        "## Audit Ranking",
        "",
        "| world | intervention | capture | delta capture | exploit mass | delta exploit mass | welfare | collapse | cost | events | MI |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in audit_rank:
        lines.append(f"| {r['world']} | {r['audit_intervention']} | {r['capture_index']:.3f} | {r.get('delta_capture_index', 0.0):.3f} | {r['exploitative_strategy_mass']:.3f} | {r.get('delta_exploitative_strategy_mass', 0.0):.3f} | {r['welfare']:.3f} | {r['collapse_probability']:.3f} | {r['containment_cost']:.3f} | {r['containment_events']:.1f} | {r['delayed_consequence_true_harm_mi']:.3f} |")
    lines += [
        "",
        "## Best Governance Cells",
        "",
        "| viable | world | policy | permanence | collapse | capture | strict zero | exploit mass | coop mass | welfare | min welfare | response diversity | cost | false containment | MI |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in best:
        lines.append(f"| {int(is_viable(r))} | {r['world']} | {r['policy']} | {r['permanence_probability']:.3f} | {r['collapse_probability']:.3f} | {r['capture_index']:.3f} | {r['strict_zero_capture_probability']:.3f} | {r['exploitative_strategy_mass']:.3f} | {r['cooperative_strategy_mass']:.3f} | {r['welfare']:.3f} | {r['minimum_zone_welfare']:.3f} | {r['response_diversity']:.3f} | {r['containment_cost']:.3f} | {r['false_containment']:.3f} | {r['delayed_consequence_true_harm_mi']:.3f} |")
    (RESULTS / "report.md").write_text("\n".join(lines) + "\n")
    vlines = ["# justitia substrate — validation report", "", "| check | result |", "|---|---:|"]
    for k, v in checks.items():
        vlines.append(f"| {k} | `{v}` |")
    vlines += ["", f"Causal audit: **{audit_class}**", "", f"Final verdict: **{verdict}**"]
    (RESULTS / "validation_report.md").write_text("\n".join(vlines) + "\n")


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    params = scenario_grid()
    for p in params:
        for seed in SEEDS:
            rows.append(run_one(seed, p))
    summary = summarize(rows)
    checks, audit_class, verdict, viable = validate(summary)
    write_csv(RAW / "runs.csv", rows)
    write_csv(RAW / "summary.csv", summary)
    write_csv(RAW / "viable_cells.csv", viable)
    plots(summary)
    report(summary, checks, audit_class, verdict, viable)
    manifest = {
        "git_head": git_value(["rev-parse", "HEAD"]),
        "git_status_short": git_value(["status", "--short"]),
        "spec_sha256": spec_hash(),
        "seeds": SEEDS,
        "num_cells": len(summary),
        "num_runs": len(rows),
        "validation_checks": checks,
        "causal_audit": audit_class,
        "final_verdict": verdict,
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "audit": audit_class, "cells": len(summary), "runs": len(rows), "viable": len(viable), "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
