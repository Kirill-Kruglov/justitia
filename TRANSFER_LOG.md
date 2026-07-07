# TRANSFER_LOG

Transfer test: apply fallacy-cutter to justitia using only fallacy-cutter docs
(`README.md`, `methodology/`, `examples/hello_gate/`, `gate_harness/README.md`)
plus `justitia_harnessed_replay_design.md`.

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
