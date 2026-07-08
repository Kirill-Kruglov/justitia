# TRANSFER_LOG

Transfer test: apply fallacy-cutter to justitia using only fallacy-cutter docs
(`README.md`, `methodology/`, `examples/hello_gate/`, `gate_harness/README.md`)
plus `justitia_harnessed_replay_design.md`.

## 2026-07-08 (wave 7)

1. Wave-7 durable worktree and phase boundary.
   - Looked for: where to run line-11 phase-2 active safe-to-fail probing
     without touching the `epub-export` checkout or previous wave artifacts.
   - Found: `justitia_wave7_design.md` requires branch `harnessed-wave7` from
     `main` in `/home/master/llm_projects/justitia-wave7`; main already contains
     the merged wave-6 predictive-referee outcome.
   - Assumption/action: created the requested worktree from `main`; recon will
     be no-run. Future model edits, if approved, will keep phase-1 PD code
     unchanged and add the probe channel only through an additive module/class,
     with `gate_harness/`, published `results/`, and previous harnessed wave
     directories unchanged.

2. J-N9a implementation and relock cycle.
   - Looked for: whether active probing can be added without touching phase-1
     predictive code or the published default path.
   - Found: `model/probing.py` can wrap `PredictiveBoundaryModel` additively;
     `probe_arm=off` and `probe_budget=0` return before probe candidate
     construction, isolated probe RNG, or recovery-ledger code. PA scoring uses
     continuous ensemble disagreement over predicted next-step observables; PN
     uses an isolated `Random(stable_hash(seed, "J_N9_probe", step))` stream.
   - What happened: the first J-N9a run stopped before decision because the new
     runner used non-existent seed-policy roles (`headline_replay`,
     `engineering_budget_zero`). This was a harness metadata error, not a
     scientific result.
   - Assumption/action: changed only those role labels to the documented
     `auxiliary_check`, recorded the relock cycle here, and will relock J-N9a
     before rerunning. Thresholds, comparisons, seed blocks, model code,
     `gate_harness/`, and prior wave artifacts are unchanged.

3. J-N9a accepted locally and J-N9 draft boundary.
   - Looked for: whether the relocked active-probing equivalence gate preserves
     both required neutral paths.
   - Found: J-N9a decision PASS and `verify_decision` VALID. Off-path headline
     replay matched 18/18 expected rows exactly; budget-zero identity matched
     80/80 PA/PN checks against phase-1 PD on seeds 29900-29909.
   - Assumption/action: wrote `experiments/harnessed/J_N9_active_probing/` with
     executable runner plus `PREREG_DRAFT.json` for author review only. No
     J-N9 PREREG.lock exists and no scientific J-N9 run has been started. The
     draft pins reviewer corrections: continuous observable-disagreement PA
     score, epsilon=0.10 rationale, allocation conservation by normalization,
     published-bar health constants plus margin m, and no W7 gate rationale.

## 2026-07-08 (wave 6)

1. Wave-6 durable worktree and phase boundary.
   - Looked for: where to run line-11 predictive-referee work without touching
     the `epub-export` checkout or previous wave artifacts.
   - Found: `justitia_wave6_design.md` requires branch `harnessed-wave6` from
     `main` in `/home/master/llm_projects/justitia-wave6`; main already contains
     the merged wave-5 bonded-envelope outcome.
   - Assumption/action: created the requested worktree from `main`; recon will
     be no-run. Future model edits, if approved, will be additive in a new
     module such as `model/predictive.py` plus minimal subclass subscription,
     with `gate_harness/`, published `results/`, and previous harnessed wave
     directories unchanged.

2. Predictive referee implementation and J-N8a equivalence.
   - Looked for: whether line-11 predictive-referee machinery can be added
     without changing the published path when `predictive_arm=R0`.
   - Found: J-N8a passed the locked engineering replay: 18 expected headline
     rows, 18 actual rows, exact equality true, no mismatches;
     `verify_decision` reported VALID.
   - Assumption/action: committed an additive `model/predictive.py` module and
     J-N8a runner only. Existing model files, `gate_harness/`, published
     `results/`, and previous harnessed wave directories remain unchanged.
     Predictive arms use a self-gated observable-transition forecaster; R0
     returns through the published path before predictor construction,
     calibration, transition logging, or forecast policy code.

3. J-N8/J-N8b prereg draft boundary.
   - Looked for: how to express predictive governance without adding a hidden
     truth channel or active-probing phase-2 behavior.
   - Found: the policy scan can cover predictive trigger, calibration, rollout,
     and containment functions under the usual forbidden names. PO is recorded
     as a shadow-oracle upper bound: audit access may simulate next observables,
     but policy receives only forecast fractions. The accepted semantics are
     locked into drafts: nonintervention rollout, exclusion of confounded
     preemptive predictions from calibration, and fail-closed insufficient
     evidence when fewer than five non-confounded positive harm events appear in
     the rolling window.
   - Assumption/action: wrote executable J-N8/J-N8b runners and
     `PREREG_DRAFT.json` files for author review only; they are not locks and
     no J-N8/J-N8b scientific runs have been started.

4. J-N8/J-N8b locked results.
   - Looked for: whether a self-gated predictive referee can extend the
     published C_full boundary or repair W7 false containment without reading
     strategy fields or adding active probing.
   - Found: J-N8 decision FAIL. H-L1 FAIL; H-L2 PASS; H-L3 PASS; H-L4 PASS.
     In measured W6, pressure ceilings were R0=1.2, PO=1.6, PD=1.2,
     PR=1.2, PW=1.2; W3 and W4 had no robust grid point for any arm. Thus
     PO shows headroom, but PD remains at R0. The preregistered derivation-gap
     branch fires; PO<=R0 simpliciter and PW independent safety kill do not.
   - Found: J-N8b decision FAIL on imported W7. R0 false_containment was
     0.498875; PD false_containment was 0.497500 with directional delta
     0.001375 and permanence 0.8375; PO false_containment was 0.520500 with
     permanence 0.8500. H-L5 FAIL and the recorded directional mark 0.10 was
     not approached.
   - Assumption/action: recorded both failures as citable locked outcomes.
     Gate-open shares in J-N8 were PO=0.6396, PD=0.2442, PR=0.2760,
     PW=0.0021; mean latest calibration scores were PO=0.8057, PD=0.5233,
     PR=0.5353, PW=0.4700. Large outputs were written as `.json.gz` from the
     runners.

## 2026-07-07 (wave 5)

1. Wave-5 durable worktree and phase boundary.
   - Looked for: where to run FW-3 bonded-envelope work without touching the
     `epub-export` checkout or previous wave artifacts.
   - Found: `justitia_wave5_design.md` requires branch `harnessed-wave5` from
     `main` in `/home/master/llm_projects/justitia-wave5`; main already contains
     the merged wave-4 seeded-adoption outcomes and README row.
   - Assumption/action: created the requested worktree from `main`; recon will
     be no-run and model edits, when approved, will be limited to
     `model/artifacts.py`, with `gate_harness/`, published `results/`, and
     previous `experiments/harnessed/` wave directories unchanged.

2. Bonded artifact implementation and J-N7a equivalence.
   - Looked for: whether FW-3 rolling escrow and declaration-tax mechanics can
     be layered on the existing artifact channel while leaving
     `artifact_channel=off` byte-equivalent.
   - Found: J-N7a passed the locked engineering replay: 18 expected headline
     rows, 18 actual rows, exact equality true, no mismatches;
     `verify_decision` reported VALID.
   - Assumption/action: committed bonded mechanics only in `model/artifacts.py`.
     `P0` is a non-refundable 0.25 declaration tax burned immediately; `P1-low`
     and `P1-high` use proportional rolling escrow, burn all outstanding stake
     on nonconformance, and redistribute nothing. The stake-state observable is
     public zone collateral balance, not strategy state.

3. J-N7/J-N7b prereg draft boundary.
   - Looked for: how to express FW-3 without letting the bond become a hidden
     truth channel or a beneficiary-bearing punishment.
   - Found: referee-side conformance, policy, stake settlement, tax burn, and
     stake burn can be expressed as `(Obs + declaration + public stake-state)`;
     burned resources leave the world as deflation. `k = containment_duration = 5`
     is recorded as reuse of a published horizon, not a tuned constant.
   - Assumption/action: wrote executable J-N7/J-N7b runners and
     `PREREG_DRAFT.json` files for author review only; they are not locks and
     no J-N7/J-N7b scientific runs have been started.

4. J-N7/J-N7b locked results.
   - Looked for: whether a bonded declaration envelope can recover pressure
     parity/extension and W7 specificity where free verified artifacts and seeded
     adoption failed.
   - Found: J-N7 decision FAIL. H-P1 FAIL, H-P2 L1 FAIL, H-P2 L2 FAIL,
     H-P4 FAIL, while H-P5 classified P0/P1-low/P1-high as RETAINED. Pressure
     ceilings were W6 A0=1.2, F1=1.0, P0=None, P1-low=1.0, P1-high=1.0; W3
     and W4 had no robust grid point for any arm. The P0 preregistered pattern
     is P0 fails while P1 works only weakly in W6, supporting the contingent-
     confiscation reading over pure price in this run.
   - Found: J-N7b decision FAIL on imported W7. A0 false_containment was 0.5305;
     P1-low false_containment was 0.497125 with directional delta 0.033375;
     P1-high false_containment was 0.497625 with directional delta 0.032875.
     Both are below the preregistered 0.10 directional mark and far above the
     0.20 false-containment bar, despite permanence 0.775/0.800.
   - Assumption/action: recorded both failures as citable locked outcomes. Since
     P1-low and P1-high fail J-N7 H-P2 L1 parity and fail the J-N7b H-P3
     directional condition, the FW-3 kill condition fires: the bonded-envelope
     path is empty in this substrate under the locked definitions. Large outputs
     are committed as `.json.gz`; compact checks were gzip-packed before commit.

## 2026-07-07 (wave 4)

1. Wave-4 durable worktree and phase boundary.
   - Looked for: where to run FW-2b seeded adoption without touching the
     `epub-export` checkout or previous wave artifacts.
   - Found: `justitia_wave4_design.md` requires branch `harnessed-wave4` from
     `main` in `/home/master/llm_projects/justitia-wave4`; main already contains
     the merged wave-3 artifact channel and J-N5 decisions.
   - Assumption/action: created the requested worktree from `main`; future edits
     will keep `gate_harness/`, published `results/`, and previous harnessed
     gate directories unchanged, with model changes limited to `model/artifacts.py`.

2. Seeded artifact implementation and J-N6a equivalence.
   - Looked for: whether FW-2b arms can be layered on the existing artifact
     channel while leaving `artifact_channel=off` byte-equivalent.
   - Found: J-N6a passed the locked engineering replay: 18 expected headline
     rows, 18 actual rows, exact equality true, no mismatches;
     `verify_decision` reported VALID.
   - Assumption/action: committed seeded/forced arm support in
     `model/artifacts.py`, kept `gate_harness/` unchanged, and recorded
     J-N6/J-N6b adoption/stiffness trajectories as runner outputs for future
     locked runs.

3. J-N6/J-N6b prereg draft boundary.
   - Looked for: how to express FW-2b without letting audit-only observables
     become policy inputs.
   - Found: referee-side conformance remains `(Obs + declaration)` only;
     `counterfactual_nonconformance_rate`, `envelope_binding`, declaration
     adoption, and stiffness trajectories are analysis-only outputs.
   - Assumption/action: wrote `PREREG_DRAFT.json` files for author review only;
     they are not locks and no J-N6/J-N6b scientific runs have been started.

4. J-N6/J-N6b locked results.
   - Looked for: whether seeded/forced artifact declarations produce a carrier
     under FW-2b without turning trust into policy input.
   - Found: J-N6 decision FAIL with H-S1 FAIL, H-S2 FAIL, H-S3 RETAINED.
     W6 pressure ceilings were A0=1.2, A2f=1.0, A2s=1.0, A1s=None; W3
     and W4 had no robust grid point for any arm. A1s midpoint declared share
     was 0.996, so H-S2 was not VACUOUS; the credit branch did not fire.
   - Found: J-N6b decision FAIL. On imported W7, A2f permanence was 0.800
     but false_containment was 0.496, above the locked 0.20 ceiling; A0
     false_containment was 0.511 and A2s recorded 0.492.
   - Assumption/action: recorded both failures as citable locked outcomes.
     Because A2f fails both H-S1 and H-S4, FW-2b kill_simpliciter fires: the
     seeded-adoption corner is empty in this substrate under the locked
     definitions. The J-N6 per-step adoption/stiffness trajectory is committed
     as `adoption_stiffness_trajectories.json.gz` because the raw generated JSON
     exceeds GitHub's 100 MB blob limit; `decision.json` and `j_n6_checks.json`
     are unchanged.

## 2026-07-07 (wave 3)

1. Wave-3 durable worktree and phase boundary.
   - Looked for: where to run the W8 "corner" work without touching the
     `epub-export` checkout or the published wave-2 artifacts.
   - Found: `justitia_wave3_corner_design.md` requires branch
     `harnessed-wave3` from `main` in
     `/home/master/llm_projects/justitia-wave3`.
   - Assumption/action: created the requested worktree from `main` and will
     keep recon read-only until the author approves the declaration/conformance
     design and PREREG direction.

2. J-N5a default-neutrality gate and pre-decision row-shape fix.
   - Looked for: whether the artifact channel can be added without changing the
     published headline cells when `artifact_channel=off`.
   - Found: the first locked execution did not reach `decision.json`; it failed
     before decision because artifact-only adoption list fields were present in
     default-off rows passed to the published numeric summarizer.
   - Assumption/action: treated this as an implementation error, not a gate
     verdict; committed a default-off row-shape fix, relocked J-N5a on the fixed
     implementation, and then ran the gate once. J-N5a passed 18/18 exact
     equality cells with no mismatches.

3. J-N5/J-N5b prereg draft boundary.
   - Looked for: how to express W8's two-sided channel without weakening
     blindness.
   - Found: emission is world-side behavior and may read strategy fields;
     conformance and C_full_artifacts policy are referee-side and must use only
     existing Obs fields plus declarations under the same forbidden-name scan.
   - Assumption/action: wrote `PREREG_DRAFT.json` files for author review only;
     they are not locks and no J-N5/J-N5b runs have been started.

4. J-N5/J-N5b locked results.
   - Looked for: whether verified procedural artifacts extend the published
     adversarial-pressure boundary or repair W7 specificity.
   - Found: J-N5 decision FAIL with H-C1 FAIL, H-C2 VACUOUS, H-C3 PASS. Pressure
     ceilings did not improve: W6 A0/A1/A2 all 1.2; W3 and W4 had no robust grid
     point for any arm. J-N5b decision FAIL: A2 permanence 0.875, but
     false_containment 0.534 versus A0 0.497.
   - Assumption/action: recorded both outcomes as citable negative findings. The
     joint kill-condition fires because H-C1 FAIL and H-C4 FAIL; W8/corner is
     empty in this substrate under the locked definitions.

## 2026-07-07

1. Wave-2 durable worktree and strict phase ordering.
   - Looked for: whether wave 2 should continue in the existing checkout or a
     fresh branch/worktree.
   - Found: justitia_wave2_design.md requires branch harnessed-wave2 from
     main in /home/master/llm_projects/justitia-wave2, while the original
     checkout remains on epub-export.
   - Assumption/action: created the requested durable worktree and will keep
     J-N3 on the untouched substrate before any J-N4 substrate extension.

## 2026-07-06

1. Worktree hook installation gap.
   - Looked for: how `gate_harness/install_hooks.sh` handles linked git worktrees.
   - Not found: documentation or script support for `.git` being a file that points
     at a worktree gitdir.
   - What happened: running `bash gate_harness/install_hooks.sh` failed with
     `mkdir: cannot create directory '/tmp/justitia-harnessed/.git': Not a directory`.
   - Assumption/action: kept `gate_harness/` unmodified, installed the same
     versioned `gate_harness/hooks/pre-commit` as a symlink in the real common
     git hooks directory used by the worktree, and recorded this as a transfer
     gap rather than patching the harness.

2. Domain tautology check gap.
   - Looked for: a fallacy-cutter recipe for non-numpy, domain-specific tautology
     reports when `gate_harness.tautology_check` is not appropriate.
   - Not found: a schema beyond the runner requirement that the report contain
     `construction_may_be_tautological`, with optional `information_ratio`.
   - Assumption/action: implemented a justitia-specific stdlib report that tests
     whether the no-governance baseline can clear the viability bar before
     learner/governance success is credited, and includes the known diversity
     circularity caveat from the justitia task specification.

3. Seed policy integration gap.
   - Looked for: automatic runner enforcement of `gate_harness.seed_policy`.
   - Not found: `runner.run_gate` verifies prereg, leakage, tautology, and
     evaluation-oracle only; seed policy is a separate helper.
   - Assumption/action: gate scripts call `seed_policy.enforce_seed_policy`
     themselves and include the report in the decision payload.

4. J-N2 speed-limit dial gap.
   - Looked for: existing justitia sweep dials for propagation speed, observation
     latency, intervention latency, irreversibility time, and recovery rate.
   - Found: `atlas.AXES` already includes `delay` and `t_irrev`.
   - Not found: separate propagation-speed, observation-latency,
     intervention-latency, or recovery-rate parameters in `model/substrate.py`,
     `model/families.py`, or `model/atlas.py`.
   - Assumption/action: did not add substrate parameters. Prepared J-N2 as an
     existing-dials speed-ratio gate over `delay` and `t_irrev`; the missing
     independent dials must be explicitly accepted as out of scope or specified
     by the author before any substrate change.


5. Verbatim vendor diff vs no-`__pycache__` contradiction.
   - Looked for: how to satisfy both "copy `gate_harness/` without `__pycache__`"
     and "`diff -r` against fallacy-cutter source is empty" when the source tree
     itself contains `gate_harness/__pycache__`.
   - Not found: a documented exclusion rule for the final diff command.
   - Assumption/action: kept justitia vendored `gate_harness/` free of
     `__pycache__` and treated a raw `diff -r` showing only source-side pycache as
     non-substantive. The substantive check should use an explicit pycache
     exclusion unless the source repo is cleaned by its owner.

6. Runner tautology ordering gap (fail-open caught by review).
   - Looked for: how to compute a domain tautology report when the baseline
     data is produced by the same long experiment that the gate will analyze.
   - Not found: a documented runner pattern for experiments whose tautology
     baseline only exists after the study run, while `runner.run_gate` requires
     `tautology_report` before `experiment_fn` executes.
   - What went wrong: the first J-G1 wrapper defaulted to a hardcoded
     `construction_may_be_tautological: false` on a first run, and could read
     stale snapshot data on repeat runs. That is exactly the fail-open audit
     anti-pattern described by fallacy-cutter finding #3.
   - Assumption/action: split J-G1 into a two-step protocol. `--run-study`
     creates `outputs/model_results` plus `RUN_STAMP.json` without calling the
     runner; the gate step refuses to run without a matching stamp and computes
     the tautology report from that snapshot before `run_gate`. Honest note:
     this defect was caught by external review, not mechanically by the harness.
