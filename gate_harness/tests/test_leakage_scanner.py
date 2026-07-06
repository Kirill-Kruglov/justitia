"""Unit tests for the AST leakage scanner (finding #3/#4).

Run: python3 -m gate_harness.tests.test_leakage_scanner
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gate_harness import leakage_scanner as LS  # noqa: E402


def classify_order_proxy_BUGGY(relation_metric, coords, variant):
    """Pre-repair B2 classifier: branches on the ground-truth generator label."""
    if variant == "chain" and relation_metric["f1"] >= 0.95:
        return "ORDER_1D"
    if variant == "product2d":
        return "PRODUCT_2D"
    if variant == "product3d":
        return "UNDERDIMENSIONED_FOR_2D"
    return "INCONCLUSIVE"


def classify_order_proxy_REPAIRED(relation_metric, coords):
    """Post-repair B2.1 classifier: label-free, statistics only."""
    axis_corr = abs(coords.get("axis_corr", 0.0))
    if relation_metric["f1"] >= 0.95 and axis_corr >= 0.95:
        return "ORDER_1D"
    return "INCONCLUSIVE"


def learner_reads_z_obj_via_string_key(records):
    """Leak hidden behind a dict string key — identifier-only scans miss this."""
    return [record["z_obj"] for record in records]


def clean_fit(records):
    return [record["y"] - record["u_bias_estimate"] for record in records]


def hardcoded_audit(records):
    seen = {}
    return {
        "u_uniquely_identifies_item_id": any(len(v) <= 1 for v in seen.values()),
        "learner_fit_reads_true_z_obj": False,   # hardcoded self-report
        "aux_leakage_detected": False,           # hardcoded self-report
    }


def test_scanner_catches_variant_branching():
    report = LS.scan_fit_path([classify_order_proxy_BUGGY])
    assert report["passed"] is False
    assert any(h["forbidden_name"] == "variant" for h in report["leak_hits"])
    print("  [ok] variant-branching classifier flagged")


def test_scanner_passes_repaired_classifier():
    report = LS.scan_fit_path([classify_order_proxy_REPAIRED])
    assert report["passed"] is True, report["leak_hits"]
    print("  [ok] repaired label-free classifier passes clean")


def test_scanner_catches_dict_string_key_truth_access():
    report = LS.scan_fit_path([learner_reads_z_obj_via_string_key])
    assert report["passed"] is False
    hit = next(h for h in report["leak_hits"] if h["forbidden_name"] == "z_obj")
    assert hit["access_kind"] == "string_constant"
    print("  [ok] record[\"z_obj\"] string-key leak caught")


def test_scanner_passes_clean_fit():
    assert LS.scan_fit_path([clean_fit])["passed"] is True
    print("  [ok] clean fit passes")


def test_empty_registry_fails_closed():
    report = LS.scan_fit_path([])
    assert report["passed"] is False and report["computed_by"] == "NOT_VERIFIABLE"
    print("  [ok] empty fit-path registry fails closed")


def test_assert_raises_on_leak():
    try:
        LS.assert_no_fit_path_leakage([classify_order_proxy_BUGGY])
    except LS.LeakageError:
        print("  [ok] assert_no_fit_path_leakage raises on leak")
        return
    raise AssertionError("expected LeakageError")


def test_audit_report_integrity_flags_hardcoded_fields():
    report = LS.scan_audit_report_integrity(hardcoded_audit)
    assert report["passed"] is False
    assert set(report["not_verifiable_fields"]) == {"learner_fit_reads_true_z_obj", "aux_leakage_detected"}
    assert report["fields"]["u_uniquely_identifies_item_id"]["computed_by"] == "ast_scan"
    print("  [ok] hardcoded audit fields flagged NOT_VERIFIABLE")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        print(f"- {t.__name__}")
        try:
            t()
        except AssertionError as exc:
            failed += 1
            print(f"  [FAIL] {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
