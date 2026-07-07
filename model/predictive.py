#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import math
from collections import deque
from dataclasses import dataclass

import atlas
import families

PREDICTIVE_ARMS = ["R0", "PO", "PD", "PR", "PW"]
PREDICTIVE_ENABLED_ARMS = {"PO", "PD", "PR", "PW"}
ENSEMBLE_SIZE = 9
DEFAULT_HORIZON = 2
DEFAULT_CONFIDENT_MEMBERS = 6
DEFAULT_CALIBRATION_WINDOW = 180
DEFAULT_CALIBRATION_WARMUP = 90
DEFAULT_CALIBRATION_THRESHOLD = 0.60
DEFAULT_MIN_POSITIVE_EVENTS = 5
OBS_VECTOR_FIELDS = [
    "wellness",
    "productivity",
    "recovery",
    "migration_capacity",
    "strategy_diversity",
    "response_diversity",
    "resource_concentration",
    "apparent_cooperation",
    "sag",
    "last_aid",
    "response_to_aid",
    "neighbor_delta",
]
PREDICTED_FIELDS = [
    "wellness",
    "productivity",
    "recovery",
    "strategy_diversity",
    "response_diversity",
    "resource_concentration",
    "apparent_cooperation",
    "sag",
    "last_aid",
    "response_to_aid",
    "neighbor_delta",
]


@dataclass(frozen=True)
class PredictiveParams(families.Params):
    predictive_arm: str = "R0"
    predictive_horizon: int = DEFAULT_HORIZON
    predictive_ensemble_size: int = ENSEMBLE_SIZE
    predictive_confident_members: int = DEFAULT_CONFIDENT_MEMBERS
    predictive_calibration_window: int = DEFAULT_CALIBRATION_WINDOW
    predictive_calibration_warmup: int = DEFAULT_CALIBRATION_WARMUP
    predictive_calibration_threshold: float = DEFAULT_CALIBRATION_THRESHOLD
    predictive_min_positive_events: int = DEFAULT_MIN_POSITIVE_EVENTS


@dataclass(frozen=True)
class RefereeAction:
    allocation: tuple[float, ...]
    containment: tuple[float, ...]


def _stable_unit(*parts) -> float:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    val = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    return val / float(2**64 - 1)


def _stable_signed(scale: float, *parts) -> float:
    return (2.0 * _stable_unit(*parts) - 1.0) * scale


def _clone_predictive_params(params, *, predictive_arm: str) -> PredictiveParams:
    return PredictiveParams(**{**params.__dict__, "predictive_arm": predictive_arm})


def params_for_predictive_variant(variant: str, world: str, scenario: str, predictive_arm: str = "R0", **kwargs) -> PredictiveParams:
    return _clone_predictive_params(
        atlas.params_for_variant(variant, world, scenario=scenario, **kwargs),
        predictive_arm=predictive_arm,
    )


def _obs_dict(obs) -> dict[str, list[float]]:
    return {field: [float(x) for x in getattr(obs, field)] for field in OBS_VECTOR_FIELDS}


def _dict_to_obs(values: dict[str, list[float]], step: int, global_welfare: float | None = None):
    welfare = global_welfare
    if welfare is None:
        welfare = atlas.base.safe_mean([(values["wellness"][i] + values["productivity"][i]) / 2.0 for i in range(atlas.base.ZONES)])
    return atlas.base.Obs(
        step=step,
        wellness=tuple(values["wellness"]),
        productivity=tuple(values["productivity"]),
        recovery=tuple(values["recovery"]),
        migration_capacity=tuple(values["migration_capacity"]),
        strategy_diversity=tuple(values["strategy_diversity"]),
        response_diversity=tuple(values["response_diversity"]),
        resource_concentration=tuple(values["resource_concentration"]),
        apparent_cooperation=tuple(values["apparent_cooperation"]),
        sag=tuple(values["sag"]),
        last_aid=tuple(values["last_aid"]),
        response_to_aid=tuple(values["response_to_aid"]),
        neighbor_delta=tuple(values["neighbor_delta"]),
        global_welfare=float(welfare),
    )


class LinearTransitionEnsemble:
    def __init__(self, seed: int, arm: str, members: int = ENSEMBLE_SIZE, lr: float = 0.035):
        self.seed = int(seed)
        self.arm = arm
        self.members = int(members)
        self.lr = float(lr)
        self.feature_count = 1 + len(OBS_VECTOR_FIELDS) + 6
        self.weights = []
        for member in range(self.members):
            target_weights = {}
            for target in PREDICTED_FIELDS:
                if arm == "PD":
                    target_weights[target] = [0.0 for _ in range(self.feature_count)]
                else:
                    target_weights[target] = [
                        _stable_signed(0.020 if arm == "PW" else 0.012, seed, arm, member, target, j)
                        for j in range(self.feature_count)
                    ]
            self.weights.append(target_weights)
        self.transition_index = 0

    def _features(self, obs_values: dict[str, list[float]], action: RefereeAction, zone: int, neighbors: dict[int, list[int]]) -> list[float]:
        ns = neighbors[zone]
        neighbor_wellness = atlas.base.safe_mean([obs_values["wellness"][j] for j in ns])
        neighbor_productivity = atlas.base.safe_mean([obs_values["productivity"][j] for j in ns])
        neighbor_recovery = atlas.base.safe_mean([obs_values["recovery"][j] for j in ns])
        xs = [1.0]
        xs.extend(obs_values[field][zone] for field in OBS_VECTOR_FIELDS)
        xs.extend([
            float(action.allocation[zone]),
            float(action.containment[zone]),
            neighbor_wellness,
            neighbor_productivity,
            neighbor_recovery,
            atlas.base.safe_mean(obs_values["wellness"]),
        ])
        return xs

    def _dot(self, weights: list[float], xs: list[float]) -> float:
        return sum(w * x for w, x in zip(weights, xs))

    def _bootstrap_selected(self, member: int, index: int) -> bool:
        return _stable_unit(self.seed, self.arm, "bootstrap", member, index) >= 0.33

    def update(self, obs, action: RefereeAction, next_obs, neighbors: dict[int, list[int]]) -> None:
        if self.arm != "PD":
            self.transition_index += atlas.base.ZONES
            return
        obs_values = _obs_dict(obs)
        next_values = _obs_dict(next_obs)
        for zone in range(atlas.base.ZONES):
            xs = self._features(obs_values, action, zone, neighbors)
            for member in range(self.members):
                if not self._bootstrap_selected(member, self.transition_index + zone):
                    continue
                for target in PREDICTED_FIELDS:
                    y = next_values[target][zone] - obs_values[target][zone]
                    pred = self._dot(self.weights[member][target], xs)
                    err = max(-0.25, min(0.25, y - pred))
                    self.weights[member][target] = [w + self.lr * err * x for w, x in zip(self.weights[member][target], xs)]
        self.transition_index += atlas.base.ZONES

    def predict_member_next(self, member: int, obs_values: dict[str, list[float]], action: RefereeAction, neighbors: dict[int, list[int]]) -> dict[str, list[float]]:
        out = {field: list(vals) for field, vals in obs_values.items()}
        for zone in range(atlas.base.ZONES):
            xs = self._features(obs_values, action, zone, neighbors)
            for target in PREDICTED_FIELDS:
                delta = self._dot(self.weights[member][target], xs)
                if self.arm == "PW":
                    if target in {"wellness", "productivity", "recovery", "response_to_aid", "neighbor_delta"}:
                        delta = -2.25 * abs(delta if abs(delta) > 1e-9 else 0.035)
                    elif target == "resource_concentration":
                        delta = abs(delta if abs(delta) > 1e-9 else 0.080)
                    elif target == "sag":
                        delta = abs(delta if abs(delta) > 1e-9 else 0.250)
                    else:
                        delta = 1.75 * delta
                out[target][zone] = atlas.base.clamp(obs_values[target][zone] + delta)
        if self.arm == "PW":
            # Artificially high confidence: align members toward the same bad direction.
            for zone in range(atlas.base.ZONES):
                out["neighbor_delta"][zone] = min(out["neighbor_delta"][zone], -0.055)
                out["response_to_aid"][zone] = min(out["response_to_aid"][zone], -0.045)
        return out

    def predict_harm_fraction(self, model, obs, zone: int, action: RefereeAction, horizon: int) -> float:
        hits = 0
        for member in range(self.members):
            values = _obs_dict(obs)
            predicted_bad = False
            step = int(obs.step)
            for offset in range(1, horizon + 1):
                values = self.predict_member_next(member, values, action, model.neighbors)
                predicted_obs = _dict_to_obs(values, step + offset)
                if model._reactive_bad_consequence(predicted_obs, zone):
                    predicted_bad = True
                    break
            if predicted_bad:
                hits += 1
        return hits / max(1, self.members)


class ShadowOracleForecaster:
    """Audit-only upper-bound forecaster; policy receives only forecast fractions."""

    def predict_harm_fraction(self, model, obs, zone: int, action: RefereeAction, horizon: int) -> float:
        sim = copy.deepcopy(model)
        for offset in range(1, horizon + 1):
            step = int(obs.step) + offset
            sim.current_step = step
            sim._store_pre_step()
            sim._apply_shocks(step)
            sim._apply_pending_neighbor_harm(step)
            sim_obs = sim._delayed_obs()
            for i, z in enumerate(sim.zones):
                sim._apply_zone_dynamics(z, atlas.base.BUDGET * action.allocation[i], action.allocation[i], sim_obs, i)
            sim._migrate()
            sim._update_neighbor_metrics()
            sim._update_irreversible(step)
            next_obs = sim._observe(step)
            sim.obs_queue.append(next_obs)
            if sim._reactive_bad_consequence(next_obs, zone):
                return 1.0
        return 0.0

    def update(self, obs, action: RefereeAction, next_obs, neighbors: dict[int, list[int]]) -> None:
        return None


class PredictiveBoundaryModel(atlas.BoundaryAtlasModel):
    """BoundaryAtlasModel with optional self-gated predictive containment."""

    def __init__(self, seed, params, record_trajectory: bool = False):
        super().__init__(seed, params, record_trajectory=record_trajectory)
        if not self._predictive_enabled():
            return
        arm = self._predictive_arm()
        if arm == "PO":
            self._predictive_forecaster = ShadowOracleForecaster()
        else:
            self._predictive_forecaster = LinearTransitionEnsemble(seed, arm, self._predictive_ensemble_size())
        self._predictive_last_alloc = tuple([1.0 / atlas.base.ZONES for _ in range(atlas.base.ZONES)])
        self._predictive_last_action = RefereeAction(
            allocation=self._predictive_last_alloc,
            containment=tuple([0.0 for _ in range(atlas.base.ZONES)]),
        )
        self._predictive_pending = deque()
        self._predictive_calibration = deque(maxlen=self._predictive_calibration_window())
        self.predictive_gate_open_by_step = []
        self.predictive_calibration_by_step = []
        self.predictive_harm_fraction_by_step = []
        self.predictive_preemptive_containment_events = 0
        self.predictive_reactive_containment_events = 0
        self.predictive_confounded_predictions = 0
        self.predictive_resolved_predictions = 0
        self.predictive_insufficient_evidence_steps = 0

    def _predictive_arm(self) -> str:
        return getattr(self.params, "predictive_arm", "R0")

    def _predictive_enabled(self) -> bool:
        return self._predictive_arm() in PREDICTIVE_ENABLED_ARMS

    def _predictive_horizon(self) -> int:
        return int(getattr(self.params, "predictive_horizon", DEFAULT_HORIZON))

    def _predictive_ensemble_size(self) -> int:
        return int(getattr(self.params, "predictive_ensemble_size", ENSEMBLE_SIZE))

    def _predictive_confident_members(self) -> int:
        return int(getattr(self.params, "predictive_confident_members", DEFAULT_CONFIDENT_MEMBERS))

    def _predictive_theta(self) -> float:
        return self._predictive_confident_members() / max(1, self._predictive_ensemble_size())

    def _predictive_calibration_window(self) -> int:
        return int(getattr(self.params, "predictive_calibration_window", DEFAULT_CALIBRATION_WINDOW))

    def _predictive_calibration_warmup(self) -> int:
        return int(getattr(self.params, "predictive_calibration_warmup", DEFAULT_CALIBRATION_WARMUP))

    def _predictive_min_positive_events(self) -> int:
        return int(getattr(self.params, "predictive_min_positive_events", DEFAULT_MIN_POSITIVE_EVENTS))

    def _reactive_bad_consequence(self, obs, i: int) -> bool:
        return super()._bad_consequence(obs, i)

    def _calibration_report(self) -> dict:
        n = len(self._predictive_calibration)
        positives = sum(1 for r in self._predictive_calibration if r["actual"])
        negatives = n - positives
        tp = sum(1 for r in self._predictive_calibration if r["predicted"] and r["actual"])
        tn = sum(1 for r in self._predictive_calibration if (not r["predicted"]) and (not r["actual"]))
        tpr = tp / positives if positives else 0.0
        tnr = tn / negatives if negatives else 0.0
        ba = 0.5 * (tpr + tnr) if positives and negatives else 0.0
        reason = "open"
        if n < self._predictive_calibration_warmup():
            reason = "warmup"
        elif positives < self._predictive_min_positive_events():
            reason = "insufficient_evidence"
        elif ba < float(getattr(self.params, "predictive_calibration_threshold", DEFAULT_CALIBRATION_THRESHOLD)):
            reason = "below_threshold"
        return {
            "n": n,
            "positive_harm_events": positives,
            "negative_events": negatives,
            "balanced_accuracy": ba,
            "gate_open": reason == "open",
            "reason": reason,
        }

    def _resolve_predictive_calibration(self, obs) -> dict:
        while self._predictive_pending and self._predictive_pending[0]["target_step"] <= obs.step:
            item = self._predictive_pending.popleft()
            if item["confounded"]:
                self.predictive_confounded_predictions += 1
                continue
            actual = self._reactive_bad_consequence(obs, item["zone"])
            self._predictive_calibration.append({"predicted": bool(item["predicted"]), "actual": bool(actual)})
            self.predictive_resolved_predictions += 1
        report = self._calibration_report()
        if report["reason"] == "insufficient_evidence":
            self.predictive_insufficient_evidence_steps += 1
        return report

    def _predictive_action(self) -> RefereeAction:
        return RefereeAction(
            allocation=tuple(self._predictive_last_alloc),
            containment=tuple(1.0 if z.containment_timer > 0 else 0.0 for z in self.zones),
        )

    def _predictive_harm_fraction(self, obs, i: int, action: RefereeAction) -> float:
        return self._predictive_forecaster.predict_harm_fraction(self, obs, i, action, self._predictive_horizon())

    def _record_predictive_step(self, obs, report: dict, fractions: list[float]) -> None:
        self.predictive_gate_open_by_step.append({
            "step": int(obs.step),
            "gate_open": bool(report["gate_open"]),
            "reason": report["reason"],
        })
        self.predictive_calibration_by_step.append({"step": int(obs.step), **report})
        self.predictive_harm_fraction_by_step.append({"step": int(obs.step), "fractions": list(fractions)})

    def choose_alloc(self):
        if not self._predictive_enabled():
            return super().choose_alloc()
        if not (self.params.family == "C" and self.params.policy15 in set(atlas.C_VARIANTS)):
            return super().choose_alloc()
        obs = self._delayed_obs()
        report = self._resolve_predictive_calibration(obs)
        action = self._predictive_action()
        fractions = []
        predictive_triggers = []
        reactive_triggers = []
        for i, z in enumerate(self.zones):
            reactive = self._reactive_bad_consequence(obs, i)
            fraction = self._predictive_harm_fraction(obs, i, action)
            predicted = fraction >= self._predictive_theta()
            active_predicted = bool(report["gate_open"] and predicted)
            if reactive or active_predicted:
                cost = 0.025 * self.params.containment_strength * self.params.action_channel_cost_scale
                self._record_or_apply_containment(i, z, self.params.containment_duration, cost, count_false=False)
                if reactive:
                    self.predictive_reactive_containment_events += 1
                elif active_predicted:
                    self.predictive_preemptive_containment_events += 1
            self._predictive_pending.append({
                "target_step": int(obs.step) + self._predictive_horizon(),
                "zone": i,
                "predicted": bool(predicted),
                "confounded": bool(active_predicted and not reactive),
            })
            fractions.append(fraction)
            predictive_triggers.append(active_predicted)
            reactive_triggers.append(reactive)
        self._record_predictive_step(obs, report, fractions)
        scores = [self._score_c(obs, i) for i in range(atlas.base.ZONES)]
        shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
        alloc = self._apply_cap(atlas.base.normalize(shifted), use_caps=self.params.policy15 != "C_dyn_only")
        self._predictive_last_alloc = tuple(alloc)
        self._predictive_last_action = RefereeAction(
            allocation=tuple(alloc),
            containment=tuple(1.0 if (p or r) else 0.0 for p, r in zip(predictive_triggers, reactive_triggers)),
        )
        return alloc

    def step(self, step):
        if not self._predictive_enabled():
            return super().step(step)
        obs_before = self._delayed_obs()
        super().step(step)
        obs_after = self.obs_queue[-1]
        self._predictive_forecaster.update(obs_before, self._predictive_last_action, obs_after, self.neighbors)
        return None

    def predictive_metrics(self) -> dict:
        if not self._predictive_enabled():
            return {}
        steps = max(1, len(self.predictive_gate_open_by_step))
        gate_open_share = sum(1 for r in self.predictive_gate_open_by_step if r["gate_open"]) / steps
        latest = self.predictive_calibration_by_step[-1] if self.predictive_calibration_by_step else self._calibration_report()
        return {
            "predictive_arm": self._predictive_arm(),
            "predictive_gate_open_share": gate_open_share,
            "predictive_latest_calibration_score": float(latest.get("balanced_accuracy", 0.0)),
            "predictive_latest_calibration_reason": latest.get("reason", "none"),
            "predictive_preemptive_containment_events": self.predictive_preemptive_containment_events,
            "predictive_reactive_containment_events": self.predictive_reactive_containment_events,
            "predictive_confounded_predictions": self.predictive_confounded_predictions,
            "predictive_resolved_predictions": self.predictive_resolved_predictions,
            "predictive_insufficient_evidence_steps": self.predictive_insufficient_evidence_steps,
            "predictive_gate_open_by_step": list(self.predictive_gate_open_by_step),
            "predictive_calibration_by_step": list(self.predictive_calibration_by_step),
            "predictive_harm_fraction_by_step": list(self.predictive_harm_fraction_by_step),
        }


def run_one(seed, params, axis="default", axis_value=0.0, axis_label="default", cell="core"):
    model = PredictiveBoundaryModel(seed, params)
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
    return row
