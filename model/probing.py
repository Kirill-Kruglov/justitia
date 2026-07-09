#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import random
from collections import Counter, deque
from dataclasses import dataclass

import atlas
import predictive

PROBE_ARMS = ["off", "PA", "PN"]
PROBE_ACTIVE_ARMS = {"PA", "PN"}
DEFAULT_PROBE_BUDGET = 20
DEFAULT_PROBE_EPSILON = 0.10
DEFAULT_PROBE_FREQUENCY = 5
DEFAULT_PROBE_HEALTH_MARGIN = 0.10
DEFAULT_PROBE_NON_RECOVERY_BUDGET = 0.10
DEFAULT_PROBE_MIN_RECOVERY_DENOMINATOR = 5


@dataclass(frozen=True)
class ProbeParams(predictive.PredictiveParams):
    probe_arm: str = "off"
    probe_budget: int = 0
    probe_epsilon: float = DEFAULT_PROBE_EPSILON
    probe_frequency: int = DEFAULT_PROBE_FREQUENCY
    probe_health_margin: float = DEFAULT_PROBE_HEALTH_MARGIN
    probe_non_recovery_budget: float = DEFAULT_PROBE_NON_RECOVERY_BUDGET
    probe_min_recovery_denominator: int = DEFAULT_PROBE_MIN_RECOVERY_DENOMINATOR


def _clone_probe_params(params, *, predictive_arm: str, probe_arm: str = "off", probe_budget: int = 0, **kwargs) -> ProbeParams:
    data = dict(params.__dict__)
    data.update({"predictive_arm": predictive_arm, "probe_arm": probe_arm, "probe_budget": int(probe_budget)})
    data.update(kwargs)
    return ProbeParams(**data)


def params_for_probe_variant(variant: str, world: str, scenario: str, arm: str = "PD", **kwargs) -> ProbeParams:
    probe_kwargs = {}
    for key in list(kwargs.keys()):
        if key.startswith("probe_"):
            probe_kwargs[key] = kwargs.pop(key)
    if arm == "R0":
        predictive_arm, probe_arm, budget = "R0", "off", 0
    elif arm in {"PO", "PD", "PR", "PW"}:
        predictive_arm, probe_arm, budget = arm, "off", 0
    elif arm in PROBE_ACTIVE_ARMS:
        predictive_arm, probe_arm, budget = "PD", arm, int(probe_kwargs.pop("probe_budget", DEFAULT_PROBE_BUDGET))
    else:
        raise ValueError(f"unknown probe arm: {arm}")
    params = predictive.params_for_predictive_variant(variant, world, scenario=scenario, predictive_arm=predictive_arm, **kwargs)
    return _clone_probe_params(params, predictive_arm=predictive_arm, probe_arm=probe_arm, probe_budget=budget, **probe_kwargs)


def _stable_int(*parts) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _variance(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


class ProbingPredictiveBoundaryModel(predictive.PredictiveBoundaryModel):
    """Additive active safe-to-fail probing layer over the phase-1 predictive model."""

    def __init__(self, seed, params, record_trajectory: bool = False):
        super().__init__(seed, params, record_trajectory=record_trajectory)
        if not self._probe_enabled():
            return
        self._probe_pending_recovery = deque()
        self._probe_channel_closed = False
        self._probe_channel_closed_step = None
        self._probe_events = []
        self._probe_skips = []
        self._probe_recovery_audits = []
        self._probe_non_recovery_by_step = []
        self._probe_count = 0
        self._probe_non_recovered = 0
        self._probe_resolved = 0

    def _probe_arm(self) -> str:
        return getattr(self.params, "probe_arm", "off")

    def _probe_budget(self) -> int:
        return int(getattr(self.params, "probe_budget", 0))

    def _probe_enabled(self) -> bool:
        return self._probe_arm() in PROBE_ACTIVE_ARMS and self._probe_budget() > 0 and self._predictive_arm() == "PD"

    def _probe_epsilon(self) -> float:
        return float(getattr(self.params, "probe_epsilon", DEFAULT_PROBE_EPSILON))

    def _probe_frequency(self) -> int:
        return int(getattr(self.params, "probe_frequency", DEFAULT_PROBE_FREQUENCY))

    def _probe_recovery_window(self) -> int:
        return int(getattr(self.params, "containment_duration", 5))

    def _probe_non_recovery_budget(self) -> float:
        return float(getattr(self.params, "probe_non_recovery_budget", DEFAULT_PROBE_NON_RECOVERY_BUDGET))

    def _probe_min_recovery_denominator(self) -> int:
        return int(getattr(self.params, "probe_min_recovery_denominator", DEFAULT_PROBE_MIN_RECOVERY_DENOMINATOR))

    def _probe_health_margin(self) -> float:
        return float(getattr(self.params, "probe_health_margin", DEFAULT_PROBE_HEALTH_MARGIN))

    def _probe_health_guard(self, obs, zone: int) -> bool:
        m = self._probe_health_margin()
        healthy_core = min(obs.wellness[zone], obs.productivity[zone], obs.recovery[zone]) >= 0.42 + m
        concentration_ok = obs.resource_concentration[zone] <= 0.62 - m
        neighbor_ok = obs.neighbor_delta[zone] >= -0.030 + (m / 2.0)
        response_ok = obs.response_to_aid[zone] >= -0.025 + (m / 2.0)
        current_harm_free = not self._reactive_bad_consequence(obs, zone)
        return bool(healthy_core and concentration_ok and neighbor_ok and response_ok and current_harm_free)

    def _probe_allocation(self, base_alloc, zone: int, sign: int) -> list[float]:
        alloc = list(base_alloc)
        alloc[zone] = max(0.0, alloc[zone] * (1.0 + sign * self._probe_epsilon()))
        return atlas.base.normalize(alloc)

    def _probe_action(self, allocation: list[float]) -> predictive.RefereeAction:
        prior = getattr(self, "_predictive_last_action", None)
        if prior is not None:
            containment = tuple(prior.containment)
        else:
            containment = tuple(1.0 if z.containment_timer > 0 else 0.0 for z in self.zones)
        return predictive.RefereeAction(allocation=tuple(allocation), containment=containment)

    def _continuous_disagreement_score(self, obs, allocation: list[float], zone: int) -> float:
        forecaster = getattr(self, "_predictive_forecaster", None)
        if not isinstance(forecaster, predictive.LinearTransitionEnsemble):
            return 0.0
        obs_values = predictive._obs_dict(obs)
        action = self._probe_action(allocation)
        member_predictions = [
            forecaster.predict_member_next(member, obs_values, action, self.neighbors)
            for member in range(forecaster.members)
        ]
        field_vars = []
        for field in predictive.PREDICTED_FIELDS:
            field_vars.append(_variance([float(pred[field][zone]) for pred in member_predictions]))
        return sum(field_vars) / max(1, len(field_vars))

    def _candidate_probes(self, obs, base_alloc) -> list[dict]:
        candidates = []
        for zone in range(atlas.base.ZONES):
            if not self._probe_health_guard(obs, zone):
                continue
            for sign in (1, -1):
                alloc = self._probe_allocation(base_alloc, zone, sign)
                candidates.append({
                    "zone": zone,
                    "sign": sign,
                    "allocation": alloc,
                    "score": self._continuous_disagreement_score(obs, alloc, zone),
                })
        return candidates

    def _select_probe(self, obs, base_alloc, candidates: list[dict]) -> dict:
        if self._probe_arm() == "PA":
            return max(candidates, key=lambda c: (c["score"], -c["zone"], c["sign"]))
        rng = random.Random(_stable_int(self.seed, "J_N9_probe", int(obs.step)))
        return candidates[rng.randrange(len(candidates))]

    def _record_probe_skip(self, obs, reason: str) -> None:
        self._probe_skips.append({"step": int(obs.step), "reason": reason})

    def _recovery_rate(self) -> float:
        return self._probe_non_recovered / self._probe_resolved if self._probe_resolved else 0.0

    def _resolve_probe_recovery(self, obs) -> None:
        while self._probe_pending_recovery and self._probe_pending_recovery[0]["target_step"] <= obs.step:
            item = self._probe_pending_recovery.popleft()
            recovered = self._probe_health_guard(obs, int(item["zone"]))
            self._probe_resolved += 1
            if not recovered:
                self._probe_non_recovered += 1
            rate = self._recovery_rate()
            audit = {
                **item,
                "resolved_step": int(obs.step),
                "recovered": bool(recovered),
                "non_recovery_rate": rate,
                "resolved_denominator": self._probe_resolved,
            }
            self._probe_recovery_audits.append(audit)
            self._probe_non_recovery_by_step.append({
                "step": int(obs.step),
                "non_recovery_rate": rate,
                "resolved_denominator": self._probe_resolved,
            })
            if self._probe_resolved >= self._probe_min_recovery_denominator() and rate > self._probe_non_recovery_budget():
                self._probe_channel_closed = True
                self._probe_channel_closed_step = int(obs.step)

    def choose_alloc(self):
        alloc = super().choose_alloc()
        if not self._probe_enabled():
            return alloc
        obs = self._delayed_obs()
        self._resolve_probe_recovery(obs)
        if self._probe_channel_closed:
            self._record_probe_skip(obs, "recovery_budget_exceeded")
            return alloc
        if self._probe_count >= self._probe_budget():
            self._record_probe_skip(obs, "budget_exhausted")
            return alloc
        if self._probe_frequency() <= 0 or int(obs.step) % self._probe_frequency() != 0:
            return alloc
        candidates = self._candidate_probes(obs, alloc)
        if not candidates:
            self._record_probe_skip(obs, "health_margin_guard")
            return alloc
        chosen = self._select_probe(obs, alloc, candidates)
        self._probe_count += 1
        probed_alloc = chosen["allocation"]
        action = self._probe_action(probed_alloc)
        self._predictive_last_alloc = tuple(probed_alloc)
        self._predictive_last_action = action
        event = {
            "step": int(obs.step),
            "zone": int(chosen["zone"]),
            "sign": int(chosen["sign"]),
            "epsilon": self._probe_epsilon(),
            "arm": self._probe_arm(),
            "continuous_disagreement_score": float(chosen["score"]),
            "allocation_before": [float(x) for x in alloc],
            "allocation_after": [float(x) for x in probed_alloc],
            "allocation_sum_after": float(sum(probed_alloc)),
        }
        self._probe_events.append(event)
        self._probe_pending_recovery.append({
            "probe_step": int(obs.step),
            "target_step": int(obs.step) + self._probe_recovery_window(),
            "zone": int(chosen["zone"]),
            "sign": int(chosen["sign"]),
        })
        return probed_alloc

    def probe_metrics(self) -> dict:
        if not self._probe_enabled():
            return {}
        zone_counts = Counter(str(e["zone"]) for e in self._probe_events)
        positive = sum(1 for e in self._probe_events if e["sign"] > 0)
        negative = sum(1 for e in self._probe_events if e["sign"] < 0)
        score_values = [float(e["continuous_disagreement_score"]) for e in self._probe_events]
        return {
            "probe_arm": self._probe_arm(),
            "probe_budget": self._probe_budget(),
            "probe_epsilon": self._probe_epsilon(),
            "probe_frequency": self._probe_frequency(),
            "probe_health_margin": self._probe_health_margin(),
            "probe_recovery_window": self._probe_recovery_window(),
            "probe_non_recovery_budget": self._probe_non_recovery_budget(),
            "probe_count": self._probe_count,
            "probe_count_by_zone": dict(sorted(zone_counts.items())),
            "probe_positive_count": positive,
            "probe_negative_count": negative,
            "probe_channel_closed": bool(self._probe_channel_closed),
            "probe_channel_closed_step": self._probe_channel_closed_step,
            "probe_non_recovery_rate": self._recovery_rate(),
            "probe_recovery_denominator": self._probe_resolved,
            "probe_mean_continuous_disagreement_score": sum(score_values) / len(score_values) if score_values else 0.0,
            "probe_events_by_step": list(self._probe_events),
            "probe_skips_by_step": list(self._probe_skips),
            "probe_recovery_audits": list(self._probe_recovery_audits),
            "probe_non_recovery_by_step": list(self._probe_non_recovery_by_step),
        }


def run_one(seed, params, axis="default", axis_value=0.0, axis_label="default", cell="core"):
    if getattr(params, "probe_arm", "off") == "off" or int(getattr(params, "probe_budget", 0)) <= 0:
        return predictive.run_one(seed, params, axis, axis_value, axis_label, cell)
    model = ProbingPredictiveBoundaryModel(seed, params)
    out = model.run()
    row = {
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
        "containment_timer_activity": sum(z.containment_timer for z in model.zones),
        **out,
    }
    if model._predictive_enabled():
        row["predictive_arm"] = getattr(params, "predictive_arm", "R0")
        row.update(model.predictive_metrics())
    row.update(model.probe_metrics())
    return row
