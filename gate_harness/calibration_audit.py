"""Anchor / calibration volume assertions.

Fixes audit finding #7: B2 called its anchor regime "minimal calibration" while
the "sparse" variant carried MORE anchor records (216) than the "complete"
variant (144) — sparse was topologically thin but volumetrically heavy. These
assertions make "minimal calibration" a checked claim, not a word, and fire
BEFORE any learner runs.
"""

from __future__ import annotations

from typing import Any, Sized


class CalibrationError(RuntimeError):
    """Raised when a calibration-volume claim cannot be honestly made."""


def anchor_fraction(anchor_records: Sized, non_anchor_records: Sized) -> float:
    denom = len(non_anchor_records)
    if denom == 0:
        raise CalibrationError("no non-anchor records; anchor fraction undefined (fail closed)")
    return len(anchor_records) / denom


def assert_minimal_calibration(
    anchor_records: Sized,
    non_anchor_records: Sized,
    max_anchor_fraction: float,
    max_anchor_records_absolute: int | None = None,
) -> dict[str, Any]:
    """Assert the calibration set is small enough to call 'minimal'. Fail closed.

    ``max_anchor_fraction`` is mandatory (a prereg field, never a default). If
    the observed anchor fraction exceeds it, raise — the experiment may not then
    write a 'minimal calibration' claim into its decision JSON.
    """
    if max_anchor_fraction is None:
        raise CalibrationError("max_anchor_fraction is mandatory (prereg field) — none given")
    frac = anchor_fraction(anchor_records, non_anchor_records)
    report = {
        "anchor_records": len(anchor_records),
        "non_anchor_records": len(non_anchor_records),
        "anchor_fraction": frac,
        "max_anchor_fraction": max_anchor_fraction,
        "max_anchor_records_absolute": max_anchor_records_absolute,
        "minimal_calibration_claim_allowed": True,
    }
    if frac > max_anchor_fraction:
        raise CalibrationError(
            f"anchor_fraction {frac:.3f} exceeds max_anchor_fraction "
            f"{max_anchor_fraction}: calibration is not minimal (finding #7)"
        )
    if max_anchor_records_absolute is not None and len(anchor_records) > max_anchor_records_absolute:
        raise CalibrationError(
            f"anchor_records {len(anchor_records)} exceeds absolute cap "
            f"{max_anchor_records_absolute} (finding #7)"
        )
    return report


def assert_sparse_not_heavier_than_complete(
    sparse_anchor_records: Sized,
    complete_anchor_records: Sized,
) -> dict[str, Any]:
    """Hard error if the 'sparse' regime has >= as many anchor records as 'complete'.

    This is the direct guard against finding #7 (real numbers: sparse=216 vs
    complete=144). It is meant to run at data-generation time, before any learner.
    """
    n_sparse = len(sparse_anchor_records)
    n_complete = len(complete_anchor_records)
    if n_sparse >= n_complete:
        raise CalibrationError(
            f"'sparse' anchor set has {n_sparse} records, >= 'complete' set's "
            f"{n_complete}: 'sparse' is not sparse by volume (finding #7). "
            f"A sparse regime must reduce anchor records, not just graph edges."
        )
    return {"sparse_anchor_records": n_sparse, "complete_anchor_records": n_complete, "ok": True}
