# Limitations & honest status

`justitia` is a small simulation that argues for a mechanism. It is an intuition
pump, not a proof about real governance or real multi-agent AI. What it does *not*
claim, on purpose:

## 1. It is a simulation

Every result is a statement about *this* evolvable-strategy substrate. External
validity — that anything here transfers to real institutions or real AI systems —
is a narrative leap the reader must make consciously. The honest reading is: "in a
minimal world where I can measure it, here is what blind governance required."

## 2. The result is a decomposition, not a new mechanism

The governance levers are the ablated components of an earlier experiment, cleanly
separated into "structural anti-concentration" and "consequence response." The
contribution is the conceptual separation, the per-world classification, the
boundary map, and the threshold-stability check — not a newly invented control.

## 3. The two levers are coupled by construction — state it as one mechanism

This was tested, not assumed. The load-bearing anti-concentration acts only inside
a consequence-triggered containment episode; given a structural limit with the
consequence trigger removed, it never engages (`containment_events = 0`) and the
world collapses (`permanence = 0`) in every cell. So the headline is *not* "two
independent levers, both required" — that phrasing would be a trivial tautology
given the coupling. The honest claim is a single mechanism: **consequence-gated
anti-concentration**. In this substrate you cannot realize the structural limit as
a free-standing always-on dial that works; the only thing that works is the
coupled act.

## 4. Static caps were redundant — and that is a finding

Of the two ways anti-concentration was implemented (a post-hoc allocation cap and
a limit inside the dynamics), only the dynamics form carried robustness; the cap
was redundant and, in one world, mildly harmful. The published model is the
simplified one. We keep the redundant path only as a documented ablation.

## 5. Thresholds are researcher choices (but checked)

Viability is defined by several simultaneous thresholds (welfare floor, exploit
ceiling, etc.). These are researcher degrees of freedom. We do not hide this: the
verdict is re-evaluated across a grid of perturbed thresholds, and only the
configurations that survive that perturbation are reported as stable.

## 6. Boundary failures are part of the result

Pure-capture and monoculture-shock worlds have no robust blind kernel under any
configuration tested. We report these as failures, not as worlds to be "rescued"
by widening a sweep until something passes.

## What would strengthen it further

- An interactive, in-browser version where a reader toggles the scales and the
  sword on/off per world and watches homeostasis hold or fail.
- A second substrate with different microdynamics, to see which findings are
  substrate-specific and which recur.
- A cleaner separation of the consequence signal's informativeness from its delay.
