"""gate_harness — instrumental enforcement of Ascesis gate discipline.

This package is the *executable* counterpart to the prose methodology in
``playbook_extraction/harness/``. Where those documents *describe* the rules
(pre-registration, no leakage, minimal calibration, multi-seed), this package
*enforces* them so that a violation is mechanically impossible for any honest
process (human, Codex, Claude, or other) that runs through it.

Design axiom: **fail closed.** Any ambiguity, missing artifact, or claim that
cannot be checked mechanically resolves to FAIL. Nothing PASSes by default.

Modules:
  - ``prereg``            : two-phase-commit pre-registration lock (findings #1, #2, #9)
  - ``leakage_scanner``   : AST fit-path + audit-integrity scan (findings #3, #4)
  - ``calibration_audit`` : anchor-volume assertions (finding #7)
  - ``seed_policy``       : multi-seed enforcement for core metrics (finding #8)
  - ``tautology_check``   : information-ratio + strong baselines (finding #5)
  - ``evaluation_oracle`` : ground-truth hints at eval call sites (finding #6)
  - ``runner``            : refuses to run without a valid prereg lock (findings #1/#2)
  - ``verify_decision``   : standalone provenance verifier (§1.7, closes bypass gap)
"""

__all__ = [
    "prereg",
    "leakage_scanner",
    "calibration_audit",
    "seed_policy",
    "tautology_check",
    "evaluation_oracle",
    "runner",
    "verify_decision",
]
