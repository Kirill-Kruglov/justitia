# justitia — model specification

A reproducible agent-based study of **blind governance**: can an arbiter keep an
ecosystem of freely-evolving strategies healthy without reading the agents'
hidden types, acting only through structural anti-concentration and responses to
observed consequences?

## Substrate (`substrate.py`)

- A world of `ZONES = 9` zones over `STEPS = 100` steps.
- Each zone holds lineages carrying mutable strategies. Strategies **mutate** and
  are **selected** each step. Some strategies are exploitative (capture
  resources, harm neighbours, intercept aid); their type is a **hidden label**.
- The arbiter observes only delayed, aggregate signals (wellness, productivity,
  recovery, neighbour deltas, aid responses). It never observes strategy
  parameters or the hidden exploitative label — this is asserted and checked.

## Governance levers (`governance.py`)

The arbiter may use, in combination:

- **Anti-concentration (the scales):** a structural limit on how much any zone or
  lineage may hold. Implemented two ways — a post-hoc allocation cap and a limit
  inside the zone dynamics.
- **Consequence response (the sword):** consequence-triggered containment that
  throttles flows where observed delayed harm has occurred.

## Families and worlds (`families.py`)

Three policy families, separated without adding mechanisms:

- **A — anti-concentration only** (static caps, no consequence feedback).
- **B — consequence governance only** (feedback, no fixed caps).
- **C — combined.**

Worlds stress the system differently: `W6_mutation_corridor`,
`W3_catastrophe_ambiguity`, `W4_scavenger_catastrophe`, `W2_pure_capture`,
`W5_monoculture_shock`, plus a held-out proxy world `W1` used for validation.

A run is summarized over many seeds with Wilson confidence intervals for
probabilities and normal intervals for continuous metrics. The headline metric is
**permanence** (durable, fair, uncaptured homeostasis); supporting metrics include
capture index, welfare, `minimum_zone_welfare`, strategy/response diversity,
catastrophe recovery, and the mutual information between the delayed consequence
signal and true harm.

## Boundary atlas + coupling (`atlas.py`, main entry)

For the robust worlds, `atlas.py`:

1. **Boundary frontier** — sweeps pressure axes (adversarial pressure,
   irreversibility, severity, cost, mutation, concentration, cap tightness,
   signal informativeness) to locate where the robust kernel breaks.
2. **Marginal value** — paired per-seed `permanence` gaps `C−A` and `C−B`.
3. **Decoupling** — separates the two anti-concentration implementations
   (`C_full`, `C_caps_only`, `C_dyn_only`) to find which is load-bearing.
4. **Consequence-gating ablation** — `C_dyn_no_consequence`: the structural limit
   with the consequence trigger removed, to test whether the scales can act at all
   without the sword.
5. **Threshold sensitivity** — re-classifies under a grid of viability thresholds.

## Validation gates

Every run asserts: the arbiter never observes strategy parameters; mutation and
selection actually occur; a naive feature-proxy governor fails on the held-out
world; exploitation rises under no control; Part A uses no delayed consequence and
Part B uses no fixed caps; the combination strictly dominates the singles in the
robust worlds; a boundary exists on each swept axis; the decoupling identifies a
load-bearing anti-concentration implementation; and the coupling question is
answered.

## Result (verdict BE)

Neither half alone holds. The working control is a **single coupled mechanism —
consequence-gated anti-concentration**: the structural limit engages only where
observed harm has triggered it. A structural limit without the consequence trigger
never engages (`containment_events = 0`) and the world collapses
(`permanence = 0`). An always-on allocation cap is redundant. The verdict is
threshold-stable across the adaptive/catastrophe worlds and breaks under high
adversarial pressure; pure-capture and monoculture-shock worlds admit no robust
blind kernel.

## Reproducibility

Pure standard-library Python; deterministic from integer seeds. Charts are emitted
as hand-written SVG. Each run records the git head and the sha256 of this spec.
`--smoke` runs a fast, coarse correctness pass; the full run reproduces the atlas.
