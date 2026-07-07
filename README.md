# justitia

[![CI](https://github.com/Kirill-Kruglov/justitia/actions/workflows/ci.yml/badge.svg)](https://github.com/Kirill-Kruglov/justitia/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*Justitia is blindfolded. She holds scales, and a sword — and she does not raise
the scales until the sword has felt harm.*

**[📖 Read the essay](https://kirill-kruglov.github.io/justitia/)** ([md](essay/soil-for-seeds-of-loving-grace.md) · [PDF](essay/soil-for-seeds-of-loving-grace.pdf)) · **[▶ Explore it interactively](https://kirill-kruglov.github.io/justitia/explore/)** · **[See the evidence](results/)**

A minimal simulation of **blind governance**: can an arbiter keep an ecosystem of
freely-evolving agents healthy — fair, non-collapsing, not captured by
exploiters — **without ever reading the agents' internals**? It may act only on
two things: a **structural limit on concentration** (the *scales*) and a
**response to observed consequences** (the *sword*). It never sees which agents
are "exploitative"; that label is hidden, and the code is checked to prove it.

The result is sharper than "you need both." The scales and the sword are **not
two independent dials** — of the policy families tested, the only configuration
that holds is a single coupled act: **consequence-gated anti-concentration**,
where the structural limit engages *only* where observed harm has triggered it. An always-on cap is redundant; a
structural limit that never waits for a consequence never even fires.

> **Status: thesis locked.** Distilled and hardened from a research sandbox of
> evolutionary-governance experiments (13 → 16.1).

## Why this exists

This is a tribute to Dario Amodei's *Machines of Loving Grace*, and an attempt at
the load-bearing piece it leaves light: not *what good* powerful AI could do, but
*by what mechanism* a world of powerful, evolving agents stays a heaven rather
than a hell for the powerless. `justitia` is a small, rigorous existence-argument
about that mechanism — an intuition pump you can run, not a policy proof. The
substrate even measures `minimum_zone_welfare`: the wellbeing of the *worst-off*
region. "Paradise for the powerless" is, here, a number you can watch.

## The question, made testable

- **Agents** carry mutable strategies; they mutate and are selected each step.
- Some strategies are exploitative (capture resources, harm neighbours, intercept
  aid). Their type is **hidden** from the arbiter.
- **Worlds** stress the system differently: mutation corridors, ambiguous
  catastrophes, scavenger shocks, pure capture, monoculture collapse.
- The **arbiter is blind**: it may use the *scales* (anti-concentration) and the
  *sword* (consequence response), never the hidden labels.
- We ask, across thousands of seeded runs with confidence intervals: **what does
  the blind arbiter need so the ecosystem reaches durable, fair homeostasis?**

## Findings

Across ~89,000 seeded runs with confidence intervals:

- **Neither half alone holds.** Static anti-concentration alone fails (permanence
  ≈ 0 in every key world); pure consequence response alone fails (permanence ≤
  0.17).
- **The two are one mechanism, not two levers.** Give the arbiter a structural
  anti-concentration limit *without* a consequence trigger and it never engages
  (`containment_events = 0`) and the world collapses (`permanence = 0`) in every
  cell. The working control is **consequence-gated anti-concentration**: the
  structural limit acts only where observed harm has called for it.
- **An always-on cap is redundant.** Of the two ways to implement
  anti-concentration — a post-hoc allocation cap and a limit inside the dynamics —
  only the dynamics form carries robustness; the cap adds nothing (and in one
  world is mildly harmful). The published model is the simplified one.
- **The verdict is threshold-stable.** It holds in 100% of 54 perturbed
  viability-threshold combinations — not an artifact of where the lines were drawn.
- **The boundary is mapped.** The robust kernel is insensitive to governance cost,
  catastrophe severity, mutation rate, and concentration pressure within the swept
  ranges, and breaks mainly under high **adversarial pressure** (~1.2×).
- **Boundary failures are reported, not rescued.** In a pure-capture world or
  under monoculture shock, *no* blind configuration produces a robust kernel.

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for what this does and does not
claim.

## Results & reproduction

The full study's evidence is checked in under [`results/`](results/) — read
[`results/boundary_atlas.md`](results/boundary_atlas.md) and
[`results/sensitivity_report.md`](results/sensitivity_report.md) (the **Lever
Coupling** section is the headline) without running anything.

To regenerate:

```bash
python run.py --smoke   # fast, seeded correctness pass
python run.py           # full study (~89k seeded runs; deterministic)
pytest                  # deterministic checks of the headline findings
```

Pure standard-library Python: no numpy, no plotting deps (charts are emitted as
hand-written SVG). Every run records git head, a spec hash, and a battery of
validation checks (blindness, that mutation/selection actually occur, that a
naive feature-proxy fails on a held-out world).

## What is enforced vs asserted

The difference is exactly what a skeptic should check, so it is stated plainly.

**Enforced at runtime** (computed every run; `pytest` checks the blindness ones by
name in seconds):

- *Blind observation* — every step asserts the referee's observation excludes the
  hidden strategy parameters; a violation crashes the run
  (`test_observation_is_blind_to_strategy`).
- *A feature-reading referee fails* — a proxy that tries to *govern* by reading
  who is exploitative from visible features is run and shown to fail on a
  held-out world (`test_feature_proxy_referee_fails_on_holdout_world`). Note the
  scope: a preregistered adversary battery later showed that *identification*
  from the same observation channel is possible at 0.99 held-out accuracy — see
  *Replayed through the knife* below. Blindness is a property of the policy,
  enforced at runtime; it is not an information-theoretic wall.
- Mutation and selection actually occur; exploitation rises under no control; the
  coupled mechanism strictly dominates each lever alone; decoupling identifies the
  load-bearing anti-concentration.

**True by construction** (facts about how the model is written, not measurements —
flagged as such, never counted among the runtime checks):

- There is no fixed hidden "type": exploitativeness is a derived, continuous
  property of an evolving strategy vector, bucketed only for metrics.
- The policy never reads that derived score (the scoring functions reference only
  observations and zone concentration).
- Family A uses no consequence trigger; Family B uses no fixed cap.

`python run.py --smoke` prints `integrity checks PASS (7/7)` — the seven runtime
checks only.

## Replayed through the knife (July 2026)

The study was re-run under [fallacy-cutter](https://github.com/Kirill-Kruglov/fallacy-cutter)'s
fail-closed harness — two-phase preregistration locked in git before each run,
an AST leakage scan of the policy path, seed policy, and provenance-signed
decisions that an independent verifier checks. Genuinely prospective
experiments ran alongside and after the replay, with kill-conditions fixed
before the runs, citable under any outcome. The gates live in
[`experiments/harnessed/`](experiments/harnessed/):

| gate | mode | outcome |
|---|---|---|
| [J-G1 headline replay](experiments/harnessed/J_G1_headline_replay/) | confirmatory replay of published thresholds | **PASS** — 22/22 frozen expectations; robust-kernel permanence reproduced exactly (0.8625 / 0.7125 / 1.0) |
| [J-N1 adversary battery](experiments/harnessed/J_N1_adversary_battery/) | prospective | **FAIL** (= a finding): simple classifiers identify exploitative zones from the referee's own delayed observations at up to 0.994 held-out balanced accuracy — the observables carry the information; the working policy just never reads it |
| [J-N2 speed limit](experiments/harnessed/J_N2_speed_limit/) | prospective, partial isolation | **FAIL** (= the preregistered kill firing): permanence is monotone in R = delay/t_irrev with zero violations, but equal-R configurations diverge by up to 0.417 against a 0.12 tolerance — the simple ratio account is dead |
| [J-N3 held-out world W7](experiments/harnessed/J_N3_heldout_W7/) | prospective, held-out world (designed & locked before any run) | **FAIL** (= a boundary finding): the mechanism keeps W7 alive — permanence 0.792, every viability bar cleared — and fails on specificity alone: false containment 0.520 vs the 0.20 ceiling; when catastrophe mimics exploitation, the sword loses precision |
| [J-N4a equivalence](experiments/harnessed/J_N4a_equivalence/) | engineering gate for the substrate extension | **PASS** — with the three new dials at neutral defaults, 18/18 committed headline cells reproduce exactly (no extra RNG draws on the default path) |
| [J-N4 five-dial isolation](experiments/harnessed/J_N4_five_dial_isolation/) | prospective | **FAIL** on all three preregistered hypotheses: equal response-time symmetry breaks (observation lag ≠ action lag), the conditional ratio fails in 39 groups, and even per-dial monotonicity fails — slowing harm propagation can make worlds worse |

Honesty notes, stated in each preregistration: the replay is *not* independent
replication (same forge, same hands) and does not make the original study
discovery-preregistered — it verifies reproducibility, blindness, seed
sufficiency, and non-tautology of the contrast. Every FAIL outcome is
published exactly as its kill-conditions defined it; the essay's
[Revisions](https://kirill-kruglov.github.io/justitia/#revisions) section
records what each one changed. Verify everything yourself:

```bash
python scripts/verify_all.py   # every harnessed decision must be VALID
```

## Reading the boundary atlas

In [`results/boundary_atlas.md`](results/boundary_atlas.md) each axis is labelled:

- **`none_in_range`** — the kernel did **not** break anywhere in the swept range of
  that axis. This is *wide robustness*, not a failure.
- **`bracketed`** — the kernel broke between two listed values; the boundary lies in
  that interval.

A world is **robust** when its held-out permanence clears the bar across seeds and
survives threshold perturbation. "Robust" (about a world) and `none_in_range`
(about an axis) agree; they are not in tension.

## The triptych

This repository is one panel of three, sharing a single thesis — *do not try to
certify intentions; build contact, consequences, and constraints that can be
checked* — and a single honest caveat: all three come from one forge, one author,
the same AI partners. Independent replication is invited and would outweigh any
further internal check.

- **justitia** (this repo) — what keeps a world of powerful, evolving agents
  livable when no one can read anyone's soul.
- [**proxylimen**](https://github.com/Kirill-Kruglov/proxylimen) — where a mind's
  world comes from, and where blind derivation measurably breaks.
- [**fallacy-cutter**](https://github.com/Kirill-Kruglov/fallacy-cutter) — the
  fail-closed instrument both were cut with.

## License

MIT — see [`LICENSE`](LICENSE).
