# TRANSFER_LOG

Transfer test: apply fallacy-cutter to justitia using only fallacy-cutter docs
(`README.md`, `methodology/`, `examples/hello_gate/`, `gate_harness/README.md`)
plus `justitia_harnessed_replay_design.md`.

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
