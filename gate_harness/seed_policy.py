"""Multi-seed enforcement for core metrics.

Fixes audit finding #8: the central B2/B2.1 claims (order-dimension
classification, all controls) rested on a SINGLE seed, while B1.1 had already
established 24-seed rigor. This module makes an under-seeded core metric resolve
to ``INSUFFICIENT_SEEDS`` — never PASS.

A metric declares its role in the prereg:
    {"metric": "order_dimension_classification", "role": "core", "seeds": 1}
Metrics with ``role == "core"`` must use >= MIN_SEEDS_FOR_CORE_METRIC seeds.
``role == "auxiliary_check"`` metrics are exempt.
"""

from __future__ import annotations

from typing import Any, Iterable

# Floor is the max rigor already achieved in the project (24 in B1.1); we set the
# floor to 20 so it cannot silently regress to 1 as it did in B2.
MIN_SEEDS_FOR_CORE_METRIC = 20

INSUFFICIENT_SEEDS = "INSUFFICIENT_SEEDS"


class SeedPolicyError(RuntimeError):
    pass


def core_metric_verdict(pass_fail: str, seeds_used: int) -> str:
    """Return the verdict for a core metric, downgrading to INSUFFICIENT_SEEDS."""
    if seeds_used < MIN_SEEDS_FOR_CORE_METRIC:
        return INSUFFICIENT_SEEDS
    return pass_fail


def enforce_seed_policy(metric_specs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Check every metric spec. Fail closed on malformed specs.

    Each spec: {"metric": str, "role": "core"|"auxiliary_check", "seeds": int,
                "pass_fail": "PASS"|"FAIL"}.
    Returns a verdict per metric and an overall ``admissible`` flag that is False
    if any core metric is under-seeded.
    """
    verdicts: dict[str, Any] = {}
    admissible = True
    for spec in metric_specs:
        for field in ("metric", "role", "seeds"):
            if field not in spec:
                raise SeedPolicyError(f"metric spec missing {field!r}: {spec} (fail closed)")
        role = spec["role"]
        if role not in ("core", "auxiliary_check"):
            raise SeedPolicyError(f"unknown role {role!r} for {spec['metric']!r} (fail closed)")
        seeds = int(spec["seeds"])
        if role == "core":
            verdict = core_metric_verdict(spec.get("pass_fail", "PASS"), seeds)
            if verdict == INSUFFICIENT_SEEDS:
                admissible = False
        else:
            verdict = spec.get("pass_fail", "PASS")
        verdicts[spec["metric"]] = {
            "role": role,
            "seeds_used": seeds,
            "min_required": MIN_SEEDS_FOR_CORE_METRIC if role == "core" else None,
            "verdict": verdict,
        }
    return {"per_metric": verdicts, "admissible": admissible, "min_seeds_for_core": MIN_SEEDS_FOR_CORE_METRIC}
