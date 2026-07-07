#!/usr/bin/env python3
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import atlas
import families

DECLARATION_PROPENSITY = "declaration_propensity"
DECLARATION_ENVELOPE_STIFFNESS = "declaration_envelope_stiffness"
ARTIFACT_STRATEGY_FIELDS = [DECLARATION_PROPENSITY, DECLARATION_ENVELOPE_STIFFNESS]
ARTIFACT_ARMS = ["A0", "A1", "A2", "A1s", "A2s", "A2f", "F1", "P0", "P1-low", "P1-high"]
SEEDED_ARTIFACT_ARMS = {"A1s", "A2s", "F1", "P0", "P1-low", "P1-high"}
VERIFIED_ARTIFACT_ARMS = {"A2", "A2s", "A2f", "F1", "P1-low", "P1-high"}
TRUSTED_ARTIFACT_ARMS = {"A1", "A1s", "P0"}
BONDED_ARTIFACT_ARMS = {"P1-low", "P1-high"}
P0_DECLARATION_TAX = 0.25
P1_STAKE_FRACTIONS = {"P1-low": 0.10, "P1-high": 0.40}


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


@dataclass(frozen=True)
class ArtifactStakeTranche:
    amount: float
    release_step: int
    declaration: ZoneDeclaration


def _clone_artifact_params(params, *, artifact_channel: str, artifact_arm: str) -> ArtifactParams:
    return ArtifactParams(**{
        **params.__dict__,
        "artifact_channel": artifact_channel,
        "artifact_arm": artifact_arm,
    })


def _channel_for_arm(artifact_arm: str) -> str:
    if artifact_arm == "A0":
        return "off"
    if artifact_arm in TRUSTED_ARTIFACT_ARMS:
        return "unverified"
    if artifact_arm in VERIFIED_ARTIFACT_ARMS:
        return "verified"
    raise ValueError(artifact_arm)


def params_for_artifact_variant(variant: str, world: str, scenario: str, artifact_arm: str = "A0", **kwargs) -> ArtifactParams:
    return _clone_artifact_params(
        atlas.params_for_variant(variant, world, scenario=scenario, **kwargs),
        artifact_channel=_channel_for_arm(artifact_arm),
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
    Audit-only counters are recorded for analysis and are not read by policy.
    """

    def __init__(self, seed, params, record_trajectory: bool = False):
        super().__init__(seed, params, record_trajectory=record_trajectory)
        self._artifact_declarations = {}
        self.artifact_declared_mass_by_step = []
        self.artifact_declared_zone_steps = 0
        self.artifact_nonconformant_declared_zone_steps = 0
        self.artifact_binding_events_by_step = []
        self.artifact_stiffness_by_step = []
        self.artifact_initial_zone_mass = [self._zone_mass(z) for z in self.zones]
        self.artifact_stake_balance_by_zone = [0.0 for _ in self.zones]
        self._artifact_stake_tranches = [deque() for _ in self.zones]
        self._artifact_return_due_by_zone = [0.0 for _ in self.zones]
        self._artifact_forfeit_zones_this_step = set()
        self._artifact_step_stake_deposited = 0.0
        self._artifact_step_stake_returned = 0.0
        self._artifact_step_stake_burned = 0.0
        self._artifact_step_tax_burned = 0.0
        self.artifact_stake_balance_by_step = []
        self.artifact_stake_events_by_step = []
        self.artifact_total_stake_deposited = 0.0
        self.artifact_total_stake_returned = 0.0
        self.artifact_total_stake_burned = 0.0
        self.artifact_total_tax_burned = 0.0

    def _artifact_enabled(self) -> bool:
        return getattr(self.params, "artifact_channel", "off") != "off"

    def _artifact_arm(self) -> str:
        return getattr(self.params, "artifact_arm", "A0")

    def _seeded_artifact_defaults(self) -> tuple[float, float]:
        arm = self._artifact_arm()
        if arm in SEEDED_ARTIFACT_ARMS:
            return 1.0, 0.50
        return 0.0, 0.50

    def _lineage(self, kind, mass):
        lineage = super()._lineage(kind, mass)
        if self._artifact_enabled():
            propensity, stiffness = self._seeded_artifact_defaults()
            lineage.strategy[DECLARATION_PROPENSITY] = propensity
            lineage.strategy[DECLARATION_ENVELOPE_STIFFNESS] = stiffness
        return lineage

    def _mutate_strategy(self, lineage):
        child = super()._mutate_strategy(lineage)
        if self._artifact_enabled():
            child.strategy[DECLARATION_PROPENSITY] = atlas.base.clamp(
                child.strategy.get(DECLARATION_PROPENSITY, self._seeded_artifact_defaults()[0])
                + self.rng.gauss(0.0, lineage.mutation_var)
            )
            if self._artifact_arm() == "A2f":
                child.strategy[DECLARATION_ENVELOPE_STIFFNESS] = 0.50
            else:
                child.strategy[DECLARATION_ENVELOPE_STIFFNESS] = atlas.base.clamp(
                    child.strategy.get(DECLARATION_ENVELOPE_STIFFNESS, 0.50)
                    + self.rng.gauss(0.0, lineage.mutation_var)
                )
        return child

    def _artifact_weighted(self, z, field: str, default: float) -> float:
        total = self._zone_mass(z)
        if total <= atlas.base.EPS:
            return default
        return sum(l.mass * l.strategy.get(field, default) for l in z.lineages) / total

    def _declaration_from_stiffness(self, zone: int, stiffness: float) -> ZoneDeclaration:
        stiffness = atlas.base.clamp(stiffness)
        slack = 0.080 * (1.0 - stiffness)
        return ZoneDeclaration(
            zone=zone,
            min_neighbor_delta=-0.030 - slack,
            max_resource_concentration=0.620 + slack,
        )

    def _record_artifact_audit_step(self, obs, declarations: dict[int, ZoneDeclaration], declared_mass: float, stiffness_values: list[float]) -> None:
        total_mass = sum(self._zone_mass(z) for z in self.zones) + atlas.base.EPS
        nonconforming = sum(1 for declaration in declarations.values() if not artifact_conforms(obs, declaration))
        declared_zone_steps = len(declarations)
        declared_by_zone = [1 if i in declarations else 0 for i in range(len(self.zones))]
        declared_concentrations = [obs.resource_concentration[i] for i in declarations]
        mean_declared_concentration = sum(declared_concentrations) / len(declared_concentrations) if declared_concentrations else 0.0
        max_declared_concentration = max(declared_concentrations, default=0.0)
        self.artifact_declared_zone_steps += declared_zone_steps
        self.artifact_nonconformant_declared_zone_steps += nonconforming
        mean_stiffness = sum(stiffness_values) / len(stiffness_values) if stiffness_values else 0.0
        self.artifact_declared_mass_by_step.append({
            "step": self.current_step,
            "declared_mass": declared_mass,
            "declared_share": declared_mass / total_mass,
            "declared_zones": declared_zone_steps,
            "declared_by_zone": declared_by_zone,
            "mean_declared_resource_concentration": mean_declared_concentration,
            "max_declared_resource_concentration": max_declared_concentration,
        })
        self.artifact_binding_events_by_step.append({
            "step": self.current_step,
            "declared_zone_steps": declared_zone_steps,
            "nonconforming_declared_zone_steps": nonconforming,
            "nonconformance_rate_this_step": nonconforming / declared_zone_steps if declared_zone_steps else 0.0,
        })
        self.artifact_stiffness_by_step.append({
            "step": self.current_step,
            "mean_declared_stiffness": mean_stiffness,
            "declared_zones": declared_zone_steps,
        })

    def _emit_zone_declarations(self, obs) -> dict[int, ZoneDeclaration]:
        declarations = {}
        declared_mass = 0.0
        stiffness_values = []
        arm = self._artifact_arm()
        for i, z in enumerate(self.zones):
            if arm == "A2f":
                stiffness = 0.50
                declarations[i] = self._declaration_from_stiffness(i, stiffness)
                declared_mass += self._zone_mass(z)
                stiffness_values.append(stiffness)
                continue
            propensity_default, stiffness_default = self._seeded_artifact_defaults()
            propensity = self._artifact_weighted(z, DECLARATION_PROPENSITY, propensity_default)
            if self.rng.random() >= propensity:
                continue
            stiffness = self._artifact_weighted(z, DECLARATION_ENVELOPE_STIFFNESS, stiffness_default)
            declarations[i] = self._declaration_from_stiffness(i, stiffness)
            declared_mass += self._zone_mass(z)
            stiffness_values.append(stiffness)
        self._record_artifact_audit_step(obs, declarations, declared_mass, stiffness_values)
        self._artifact_declarations = declarations
        return declarations

    def _artifact_bad_consequence(self, obs, i: int) -> bool:
        base_bad = self._bad_consequence(obs, i)
        arm = self._artifact_arm()
        if arm in VERIFIED_ARTIFACT_ARMS and i in self._artifact_forfeit_zones_this_step:
            return True
        declaration = self._artifact_declarations.get(i)
        if declaration is None:
            return base_bad
        if arm in TRUSTED_ARTIFACT_ARMS:
            return False
        if arm in VERIFIED_ARTIFACT_ARMS:
            return not artifact_conforms(obs, declaration)
        return base_bad

    def _escrow_window(self) -> int:
        return int(getattr(self.params, "containment_duration", 5))

    def _artifact_stake_fraction(self) -> float:
        arm = self._artifact_arm()
        if arm == "P0":
            return P0_DECLARATION_TAX
        return P1_STAKE_FRACTIONS.get(arm, 0.0)

    def _bonded_escrow_enabled(self) -> bool:
        return self._artifact_arm() in BONDED_ARTIFACT_ARMS

    def _burn_zone_stake(self, zone: int) -> float:
        burned = sum(tranche.amount for tranche in self._artifact_stake_tranches[zone])
        self._artifact_stake_tranches[zone].clear()
        self.artifact_stake_balance_by_zone[zone] = 0.0
        self.artifact_total_stake_burned += burned
        self._artifact_step_stake_burned += burned
        return burned

    def _settle_artifact_stakes(self, obs, declarations: dict[int, ZoneDeclaration]) -> None:
        self._artifact_forfeit_zones_this_step = set()
        if not self._bonded_escrow_enabled():
            return
        for i, tranches in enumerate(self._artifact_stake_tranches):
            current_declaration = declarations.get(i)
            violates = any(not artifact_conforms(obs, tranche.declaration) for tranche in tranches)
            if current_declaration is not None and not artifact_conforms(obs, current_declaration):
                violates = True
            if violates:
                self._artifact_forfeit_zones_this_step.add(i)
                self._burn_zone_stake(i)
                continue
            if not tranches:
                continue
            returned = 0.0
            while tranches and tranches[0].release_step <= self.current_step:
                returned += tranches.popleft().amount
            if returned > 0.0:
                self._artifact_return_due_by_zone[i] += returned
                self.artifact_stake_balance_by_zone[i] = max(0.0, self.artifact_stake_balance_by_zone[i] - returned)
                self.artifact_total_stake_returned += returned
                self._artifact_step_stake_returned += returned

    def _record_stake_step(self) -> None:
        if not self._artifact_enabled():
            return
        balances = list(self.artifact_stake_balance_by_zone)
        self.artifact_stake_balance_by_step.append({
            "step": self.current_step,
            "stake_balance_by_zone": balances,
            "total_stake_balance": sum(balances),
            "stake_deposited": self._artifact_step_stake_deposited,
            "stake_returned": self._artifact_step_stake_returned,
            "stake_burned": self._artifact_step_stake_burned,
            "tax_burned": self._artifact_step_tax_burned,
        })
        self.artifact_stake_events_by_step.append({
            "step": self.current_step,
            "forfeit_zones": sorted(self._artifact_forfeit_zones_this_step),
            "return_due_by_zone": list(self._artifact_return_due_by_zone),
        })

    def step(self, step):
        if not self._artifact_enabled():
            return super().step(step)
        self._artifact_step_stake_deposited = 0.0
        self._artifact_step_stake_returned = 0.0
        self._artifact_step_stake_burned = 0.0
        self._artifact_step_tax_burned = 0.0
        self._artifact_forfeit_zones_this_step = set()
        try:
            return super().step(step)
        finally:
            self._record_stake_step()

    def _apply_zone_dynamics(self, z, raw_aid, alloc_share, obs, idx):
        if not self._artifact_enabled():
            return super()._apply_zone_dynamics(z, raw_aid, alloc_share, obs, idx)
        aid_for_zone = raw_aid + self._artifact_return_due_by_zone[idx]
        self._artifact_return_due_by_zone[idx] = 0.0
        declaration = self._artifact_declarations.get(idx)
        if declaration is not None:
            arm = self._artifact_arm()
            fraction = self._artifact_stake_fraction()
            if arm == "P0" and fraction > 0.0:
                burned_tax = raw_aid * fraction
                aid_for_zone -= burned_tax
                self.artifact_total_tax_burned += burned_tax
                self._artifact_step_tax_burned += burned_tax
            elif arm in BONDED_ARTIFACT_ARMS and fraction > 0.0:
                stake = raw_aid * fraction
                aid_for_zone -= stake
                if idx in self._artifact_forfeit_zones_this_step:
                    self.artifact_total_stake_burned += stake
                    self._artifact_step_stake_burned += stake
                else:
                    tranche = ArtifactStakeTranche(
                        amount=stake,
                        release_step=self.current_step + self._escrow_window(),
                        declaration=declaration,
                    )
                    self._artifact_stake_tranches[idx].append(tranche)
                    self.artifact_stake_balance_by_zone[idx] += stake
                    self.artifact_total_stake_deposited += stake
                    self._artifact_step_stake_deposited += stake
        return super()._apply_zone_dynamics(z, max(0.0, aid_for_zone), alloc_share, obs, idx)

    def choose_alloc(self):
        if not self._artifact_enabled():
            return super().choose_alloc()
        if self.params.family == "C" and self.params.policy15 in set(atlas.C_VARIANTS):
            obs = self._delayed_obs()
            declarations = self._emit_zone_declarations(obs)
            self._settle_artifact_stakes(obs, declarations)
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
        stiffness_rows = list(self.artifact_stiffness_by_step)
        binding_rows = list(self.artifact_binding_events_by_step)
        mean_share = sum(r["declared_share"] for r in rows) / len(rows) if rows else 0.0
        max_share = max((r["declared_share"] for r in rows), default=0.0)
        mean_declared_concentration = sum(r.get("mean_declared_resource_concentration", 0.0) for r in rows) / len(rows) if rows else 0.0
        max_declared_concentration = max((r.get("max_declared_resource_concentration", 0.0) for r in rows), default=0.0)
        last_quarter = rows[int(len(rows) * 0.75):] if rows else []
        last_quarter_declared_share = sum(r["declared_share"] for r in last_quarter) / len(last_quarter) if last_quarter else 0.0
        mean_stiffness = sum(r["mean_declared_stiffness"] for r in stiffness_rows if r["declared_zones"] > 0)
        stiffness_den = sum(1 for r in stiffness_rows if r["declared_zones"] > 0)
        mean_stiffness = mean_stiffness / stiffness_den if stiffness_den else 0.0
        nonconformance_rate = (
            self.artifact_nonconformant_declared_zone_steps / self.artifact_declared_zone_steps
            if self.artifact_declared_zone_steps else 0.0
        )
        return {
            "declared_mass_by_step": rows,
            "stiffness_by_step": stiffness_rows,
            "binding_events_by_step": binding_rows,
            "mean_declared_share": mean_share,
            "max_declared_share": max_share,
            "mean_declared_resource_concentration": mean_declared_concentration,
            "max_declared_resource_concentration": max_declared_concentration,
            "last_quarter_declared_share": last_quarter_declared_share,
            "mean_declared_stiffness": mean_stiffness,
            "declared_zone_steps": self.artifact_declared_zone_steps,
            "nonconforming_declared_zone_steps": self.artifact_nonconformant_declared_zone_steps,
            "counterfactual_nonconformance_rate": nonconformance_rate,
            "realized_nonconformance_rate": nonconformance_rate,
            "envelope_binding": nonconformance_rate,
            "artifact_initial_zone_mass": list(self.artifact_initial_zone_mass),
            "artifact_stake_balance_by_zone": list(self.artifact_stake_balance_by_zone),
            "stake_balance_by_step": list(self.artifact_stake_balance_by_step),
            "stake_events_by_step": list(self.artifact_stake_events_by_step),
            "total_stake_deposited": self.artifact_total_stake_deposited,
            "total_stake_returned": self.artifact_total_stake_returned,
            "total_stake_burned": self.artifact_total_stake_burned,
            "total_tax_burned": self.artifact_total_tax_burned,
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
