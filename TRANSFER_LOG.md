# TRANSFER_LOG

Transfer test: apply fallacy-cutter to justitia using only fallacy-cutter docs
(`README.md`, `methodology/`, `examples/hello_gate/`, `gate_harness/README.md`)
plus `justitia_harnessed_replay_design.md`.

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
