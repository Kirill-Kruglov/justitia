# Post-hoc diagnostic: is H-M5's non-recovery probe-attributable?

**Status: INFERENCE, not a gate.** This diagnostic was run *after* the locked
J-N9 decision (FAIL, both preregistered kill branches fired) and does not
alter that verdict. It informs the reading and any future preregistration.

## Question

J-N9's safety audit recorded non-recovery ≈ 0.80 against the preregistered
0.10 budget, closing the probe channel in ~89% of PA/PN runs. Is that rate
caused by the probes — or is it the baseline churn of the world, measured by
the same criterion?

## Method

Sham probes: identical guard, schedule, selection, and recovery audit, but
the allocation perturbation is **not applied** (`_probe_allocation` returns
the base allocation unchanged). The sham non-recovery rate is therefore the
rate at which a guard-passing healthy zone fails the same health-margin
criterion r=5 steps later with **no intervention at all**.

Scope: W6, pressures {1.0, 1.2}, seeds 29000–29019, real vs sham
(`diagnostics_sham_probe.py`; deterministic).

## Result

| arm | resolved probes | non-recovery |
|---|---:|---:|
| real probes (ε = 0.10) | 200 | 0.8800 |
| sham probes (no perturbation) | 200 | 0.8700 |
| **probe-attributable excess** | | **+0.0100** |

## Reading

- The H-M5 criterion measured the world's volatility, not probe harm. A
  healthy W6 zone at these pressures fails the admission margin within 5
  steps ~87% of the time on its own. The probes themselves were essentially
  harmless (excess +0.01) — consistent with PA's ceiling equalling R0 rather
  than narrowing.
- The preregistered 0.10 budget implicitly assumed near-zero baseline churn.
  That assumption is false in this substrate, so the audit closed the channel
  after ~5 probes per run — which also strangled the contact experiment:
  H-M1's null (PA ≈ PD, calibration 0.518 vs 0.520) was measured under
  almost no additional contact.
- The lesson, in the knife's own vocabulary: **an audit without a
  counterfactual control measures the world, not the intervention.** Every
  channel in this program got a null arm (PR in J-N8, PN in J-N9); the safety
  audit itself did not. Any phase-2b design must preregister a
  counterfactual-controlled recovery criterion (e.g., sham-adjusted, or
  paired unprobed control zones) — as a new gate, not a rescue of this one.

The J-N9 verdict stands exactly as locked: FAIL, mechanism branch and safety
branch both fired.
