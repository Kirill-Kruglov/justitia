# gate_harness — instrumental gate discipline

Executable enforcement of the Ascesis methodology. Where
`playbook_extraction/harness/` *describes* the rules in prose, this package
*enforces* them so a violation is mechanically impossible for any honest process
(human, Codex, Claude, or other) running through it.

**Axiom: fail closed.** Any ambiguity, missing artifact, or claim that cannot be
checked mechanically resolves to **FAIL**. Nothing passes by default.

Each module maps to a finding from the B1/B1.1/B2/B2.1 falsification audit.

## Built (backbone) — verified by `tests/test_gate_harness.py` (8/8)

### `prereg.py` — two-phase-commit pre-registration (findings #1, #2, #9)
- `lock_prereg(gate, thresholds, rationale_for_any_threshold_changes)` writes
  `PREREG.json` + `PREREG.lock` (SHA256 + timestamp + git rev at lock time).
  A threshold shared with the previous gate that changed value **requires** a
  non-empty rationale, else it raises and writes nothing (finding #9).
- `verify_prereg_lock(gate_dir)` (runner uses this) refuses to run unless the
  lock exists, its SHA matches `PREREG.json`, and the lock's rev is a **strict
  ancestor** of HEAD — i.e. the prereg was committed *before* the run (finding #1).

### `hooks/pre-commit` + `install_hooks.sh` — commit-time enforcement
- Rejects committing a gate's `PREREG.*` together with its `outputs/` (finding #1).
- Rejects editing a locked `PREREG.json` (SHA mismatch vs `PREREG.lock`, finding #2).
- Install with `bash gate_harness/install_hooks.sh` (refuses to clobber an
  existing different hook). **Not auto-installed** — it changes commit behavior.

### `leakage_scanner.py` — AST fit-path audit (findings #3, #4, #6)
- Real static analysis, **not** self-report. Scans every registered fit/predict/
  classify function's AST for forbidden truth names appearing as parameters,
  identifiers, attributes, **dict string keys** (`record["z_obj"]`), string
  constants, closures, or referenced globals.
- Catching dict-string-keys is why AST is required: the toy worlds read truth via
  `record["z_obj"]`, which an identifier-only or `pattern in source` scan misses.
- Every emitted field carries `computed_by: ast_scan` with file+line evidence, or
  `NOT_VERIFIABLE` — which makes the check FAIL, never a silent skip.
- Regression test reproduces the real B2 leak (`variant`-branching classifier),
  proves it is caught, and proves the repaired label-free version passes.

### `calibration_audit.py` — anchor-volume assertions (finding #7)
- `assert_minimal_calibration(...)` fails if the anchor fraction exceeds a
  mandatory `max_anchor_fraction`; `assert_sparse_not_heavier_than_complete(...)`
  hard-errors if "sparse" carries >= as many anchor records as "complete".
- Verified on the real B2 counts: sparse=216 >= complete=144 → raises.

### `seed_policy.py` — multi-seed enforcement (finding #8)
- `role: core` metrics need >= `MIN_SEEDS_FOR_CORE_METRIC` (=20) seeds, else the
  verdict is `INSUFFICIENT_SEEDS`, never PASS. `auxiliary_check` metrics exempt.

### `tautology_check.py` — construction pre-check (finding #5, recovered §1.6)
- `tautology_precheck(y, z, thresholds)` computes `information_ratio = var(y)/var(z)`
  before any learner; `information_ratio_min` is mandatory (no default → raises).
  Below it → immutable `construction_may_be_tautological: true`.
- `run_generic_baselines(...)` runs the two mandatory strong baselines (k-means at
  known group count; BIC-selected 1D GMM, hand-rolled — numpy only) and emits the
  verbatim honesty statement with N substituted.
- On the real B1.1 world: `information_ratio=0.0475`, both baselines abs_corr≈0.21.

### `runner.py` — execution gate (findings #1/#2)
- `run_gate(gate_dir, experiment_fn, tautology_report=...)` calls
  `verify_prereg_lock` and hard-fails (RunnerError) unless the lock is valid and
  an ancestor of HEAD. Copies the tautology flag verbatim; forbids experiment
  override.

### Adversarial self-tests — `tests/test_adversarial.py` (7/7)
Each test reproduces a real audit finding and is RED without its defense, GREEN
with it (tests 1/3/4 were already GREEN from the backbone layer — not faked-red).

### `evaluation_oracle.py` — ground-truth-at-eval detection (finding #6, §1.4)
- `scan_evaluation_call_sites(module, entrypoint_names)` walks the full module AST
  and flags ground-truth hints (e.g. `truth_axes=3`) passed as keyword args or
  dict-literal values to evaluation entrypoints. A literal constant at the call
  site is flagged `hint_value_is_literal_constant: true` (a human wrote the answer
  into the harness call). `scan_non_entrypoints` fit-path-scans everything that is
  not a declared entrypoint. Verified on the real B2 call site:
  `truth_axes=3` at `relational_order_toy.py:495`.
- `runner.run_gate` folds the oracle log into `decision.json`: any hint sets
  `classification_success_depends_on_harness_hint: true` plus the verbatim
  "NOT evidence of unsupervised recovery" warning — a harness-only field.

### `verify_decision.py` — provenance verifier (§1.7)
- `verify_decision(decision)` rejects any `decision.json` with no
  `_harness_provenance`, a mismatched `harness_version`, or a false/missing
  verified flag — so a gate that bypassed the runner cannot be cited no matter how
  good its numbers look. The verifier is deliberately a *separate* module from the
  runner it checks. Adversarial test #8.

## Integration status

`runner.py` end-to-end run of a real gate (B1 first) is the true system test —
isolated green unit tests are necessary but not sufficient. See
`experiments/B/B1_harness_rerun/` once that run exists.
