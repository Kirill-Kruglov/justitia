#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass

import atlas
import families

DECLARATION_PROPENSITY = "declaration_propensity"
DECLARATION_ENVELOPE_STIFFNESS = "declaration_envelope_stiffness"
ARTIFACT_STRATEGY_FIELDS = [DECLARATION_PROPENSITY, DECLARATION_ENVELOPE_STIFFNESS]
ARTIFACT_ARMS = ["A0", "A1", "A2"]


@dataclass(frozen=True)
class ArtifactParams(families.Params):
    artifact_channel: str = "off"
    artifact_arm: str = "A0"


@dataclass(frozen=True)
class ZoneDeclaration:
    zone: int
    min_neighbor_delta: float
    max_resource_concentration: float
    declared: bool = True


def _clone_artifact_params(params, *, artifact_channel: str, artifact_arm: str) -> ArtifactParams:
    return ArtifactParams(**{
        **params.__dict__,
        "artifact_channel": artifact_channel,
        "artifact_arm": artifact_arm,
    })


def params_for_artifact_variant(variant: str, world: str, scenario: str, artifact_arm: str = "A0", **kwargs) -> ArtifactParams:
    channel = "off" if artifact_arm == "A0" else ("unverified" if artifact_arm == "A1" else "verified")
    return _clone_artifact_params(
        atlas.params_for_variant(variant, world, scenario=scenario, **kwargs),
        artifact_channel=channel,
        artifact_arm=artifact_arm,
    )


def artifact_conforms(obs, declaration: ZoneDeclaration) -> bool:
    i = declaration.zone
    return (
        bool(declaration.declared)
        and obs.neighbor_delta[i] >= declaration.min_neighbor_delta
        and obs.resource_concentration[i] <= declaration.max_resource_concentration
    )


class ArtifactBoundaryModel(atlas.BoundaryAtlasModel):
    """BoundaryAtlasModel with an optional zone-level artifact channel.

    World-side emission may read strategy fields, mirroring extraction and other
    agent behavior. Referee-side conformance and policy code only read Obs plus
    declarations, and are the functions that gates include in the leakage scan.
    """

    def __init__(self, seed, params, record_trajectory: bool = False):
        super().__init__(seed, params, record_trajectory=record_trajectory)
        self._artifact_declarations = {}
        self.artifact_declared_mass_by_step = []

    def _artifact_enabled(self) -> bool:
        return getattr(self.params, "artifact_channel", "off") != "off"

    def _lineage(self, kind, mass):
        lineage = super()._lineage(kind, mass)
        if self._artifact_enabled():
            lineage.strategy[DECLARATION_PROPENSITY] = 0.0
            lineage.strategy[DECLARATION_ENVELOPE_STIFFNESS] = 0.50
        return lineage

    def _mutate_strategy(self, lineage):
        child = super()._mutate_strategy(lineage)
        if self._artifact_enabled():
            child.strategy[DECLARATION_PROPENSITY] = atlas.base.clamp(
                child.strategy.get(DECLARATION_PROPENSITY, 0.0) + self.rng.gauss(0.0, lineage.mutation_var)
            )
            child.strategy[DECLARATION_ENVELOPE_STIFFNESS] = atlas.base.clamp(
                child.strategy.get(DECLARATION_ENVELOPE_STIFFNESS, 0.50) + self.rng.gauss(0.0, lineage.mutation_var)
            )
        return child

    def _artifact_weighted(self, z, field: str, default: float) -> float:
        total = self._zone_mass(z)
        if total <= atlas.base.EPS:
            return default
        return sum(l.mass * l.strategy.get(field, default) for l in z.lineages) / total

    def _emit_zone_declarations(self, obs) -> dict[int, ZoneDeclaration]:
        declarations = {}
        declared_mass = 0.0
        total_mass = sum(self._zone_mass(z) for z in self.zones) + atlas.base.EPS
        for i, z in enumerate(self.zones):
            propensity = self._artifact_weighted(z, DECLARATION_PROPENSITY, 0.0)
            if self.rng.random() >= propensity:
                continue
            stiffness = self._artifact_weighted(z, DECLARATION_ENVELOPE_STIFFNESS, 0.50)
            slack = 0.080 * (1.0 - stiffness)
            declarations[i] = ZoneDeclaration(
                zone=i,
                min_neighbor_delta=-0.030 - slack,
                max_resource_concentration=0.620 + slack,
            )
            declared_mass += self._zone_mass(z)
        self.artifact_declared_mass_by_step.append({
            "step": self.current_step,
            "declared_mass": declared_mass,
            "declared_share": declared_mass / total_mass,
            "declared_zones": len(declarations),
        })
        self._artifact_declarations = declarations
        return declarations

    def _artifact_bad_consequence(self, obs, i: int) -> bool:
        base_bad = self._bad_consequence(obs, i)
        declaration = self._artifact_declarations.get(i)
        if declaration is None:
            return base_bad
        arm = getattr(self.params, "artifact_arm", "A0")
        if arm == "A1":
            return False
        if arm == "A2":
            return not artifact_conforms(obs, declaration)
        return base_bad

    def choose_alloc(self):
        if not self._artifact_enabled():
            return super().choose_alloc()
        if self.params.family == "C" and self.params.policy15 in set(atlas.C_VARIANTS):
            obs = self._delayed_obs()
            self._emit_zone_declarations(obs)
            scores = [self._score_c(obs, i) for i in range(atlas.base.ZONES)]
            for i, z in enumerate(self.zones):
                if self._artifact_bad_consequence(obs, i):
                    self._record_or_apply_containment(
                        i,
                        z,
                        self.params.containment_duration,
                        0.025 * self.params.containment_strength * self.params.action_channel_cost_scale,
                        count_false=False,
                    )
            shifted = [max(0.01, s - min(scores) + 0.04) for s in scores]
            return self._apply_cap(atlas.base.normalize(shifted), use_caps=self.params.policy15 != "C_dyn_only")
        return super().choose_alloc()

    def artifact_adoption_metrics(self) -> dict:
        rows = list(self.artifact_declared_mass_by_step)
        mean_share = sum(r["declared_share"] for r in rows) / len(rows) if rows else 0.0
        max_share = max((r["declared_share"] for r in rows), default=0.0)
        return {
            "declared_mass_by_step": rows,
            "mean_declared_share": mean_share,
            "max_declared_share": max_share,
        }


def run_one(seed, params, axis="default", axis_value=0.0, axis_label="default", cell="core"):
    model = ArtifactBoundaryModel(seed, params)
    out = model.run()
    containment_timer_activity = sum(z.containment_timer for z in model.zones)
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
        "containment_timer_activity": containment_timer_activity,
        **out,
    }
    if getattr(params, "artifact_channel", "off") != "off":
        row.update({
            "artifact_arm": params.artifact_arm,
            "artifact_channel": params.artifact_channel,
            **model.artifact_adoption_metrics(),
        })
    return row
