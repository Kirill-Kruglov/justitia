# justitia wave 3 W8 final report

Status: locked runs completed; every outcome is reported as observed. The joint kill-condition fires because H-C1 FAIL and H-C4 FAIL.

## Gate Verdicts

| gate | decision | hypothesis vector | key note |
|---|---|---|---|
| J-N5a artifact equivalence | PASS | engineering | 18/18 exact-equal J-G1 headline cells; no mismatches |
| J-N5 corner artifacts | FAIL | H-C1 FAIL; H-C2 VACUOUS; H-C3 PASS | domain did not extend; verification question was VACUOUS because neither A1 nor A2 beat A0 |
| J-N5b W7 artifacts | FAIL | H-C4 FAIL | A2 permanence held, but false containment did not improve |

## Pressure Ceilings

| world | A0 ceiling | A1 ceiling | A2 ceiling |
|---|---:|---:|---:|
| W6_mutation_corridor | 1.2 | 1.2 | 1.2 |
| W3_catastrophe_ambiguity | none | none | none |
| W4_scavenger_catastrophe | none | none | none |

Ceiling definition: highest published adversarial_pressure grid point meeting the published robust-cell bar. Published grid: 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8.

## W7 Specificity

| arm | permanence | false_containment | threshold note |
|---|---:|---:|---|
| A0 | 0.875 | 0.497 | H-C4 requires A2 false_containment <= 0.200 and permanence >= 0.672 |
| A2 | 0.875 | 0.534 | H-C4 requires A2 false_containment <= 0.200 and permanence >= 0.672 |

A0 minus A2 false_containment delta: -0.038; negative means A2 was worse on specificity.

## Adoption Dynamics

| gate | arm | mean declared share | max declared share | note |
|---|---|---:|---:|---|
| J-N5 | A0 | 0.0000 | 0.0000 | channel off |
| J-N5 | A1 | 0.0030 | 0.2671 | nonzero adoption from initial propensity 0.0, but too weak/no domain gain |
| J-N5 | A2 | 0.0029 | 0.2672 | nonzero adoption from initial propensity 0.0, but too weak/no domain gain |
| J-N5b | A0 | 0.0000 | 0.0000 | channel off |
| J-N5b | A2 | 0.0027 | 0.1617 | nonzero adoption from initial propensity 0.0, but specificity did not improve |

## Verification

scripts/verify_all.py:

```text
VALID   experiments/harnessed/J_G1_headline_replay/decision.json
VALID   experiments/harnessed/J_N1_adversary_battery/decision.json
VALID   experiments/harnessed/J_N2_speed_limit/decision.json
VALID   experiments/harnessed/J_N3_heldout_W7/decision.json
VALID   experiments/harnessed/J_N4_five_dial_isolation/decision.json
VALID   experiments/harnessed/J_N4a_equivalence/decision.json
VALID   experiments/harnessed/J_N5_corner_artifacts/decision.json
VALID   experiments/harnessed/J_N5a_artifact_equivalence/decision.json
VALID   experiments/harnessed/J_N5b_W7_artifacts/decision.json
```

gate_harness diff against main: empty.

## TRANSFER_LOG delta

TRANSFER_LOG records the J-N5/J-N5b locked-result outcome and the joint kill-condition status.

## Git Log

```text
a61f73a Record J-N5b W7 artifact result
56271e4 Record J-N5 corner artifact result
c094a49 Lock J-N5b W7 artifact prereg
bd72d81 Lock J-N5 artifact prereg
8fe9d4d Add J-N5 artifact gate runners
cbf0bf3 Draft J-N5 artifact preregs for review
b1d05bf Record J-N5a artifact equivalence PASS
991d796 Relock J-N5a after off-path fix
90b0905 Fix W8 artifact off-path row shape
92719ec Lock J-N5a artifact equivalence prereg
a9f784a Add W8 artifact channel and equivalence gate
d501179 Start wave 3 transfer log
```
