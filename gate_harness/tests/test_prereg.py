"""Unit tests for two-phase-commit pre-registration (findings #1, #2, #9).

Run: python3 -m gate_harness.tests.test_prereg
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gate_harness import prereg as PR  # noqa: E402


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _init_repo(repo: Path):
    _run(["git", "init", "-q"], repo)
    _run(["git", "config", "user.email", "t@t"], repo)
    _run(["git", "config", "user.name", "t"], repo)


def test_prereg_lock_and_two_phase_flow():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_repo(repo)
        exp = repo / "experiments" / "G1"
        exp.mkdir(parents=True)
        (repo / "seed.txt").write_text("x")
        _run(["git", "add", "."], repo)
        _run(["git", "commit", "-q", "-m", "init"], repo)

        cwd0 = os.getcwd(); os.chdir(repo)
        try:
            PR.lock_prereg("G1", {"corr_min": 0.9}, experiments_root=repo / "experiments")
        finally:
            os.chdir(cwd0)

        ok, reason = PR.verify_prereg_lock(exp)
        assert ok is False and "finding #1" in reason
        print("  [ok] verify fails before prereg committed")

        _run(["git", "add", "experiments/G1/PREREG.json", "experiments/G1/PREREG.lock"], repo)
        _run(["git", "commit", "-q", "-m", "lock prereg"], repo)

        ok, reason = PR.verify_prereg_lock(exp)
        assert ok is True, reason
        print("  [ok] verify passes once prereg committed before run")

        (exp / "PREREG.json").write_text('{"thresholds": {"corr_min": 0.5}}\n')
        ok, reason = PR.verify_prereg_lock(exp)
        assert ok is False and "SHA" in reason
        print("  [ok] post-hoc PREREG edit detected via SHA mismatch")


def test_prereg_threshold_change_requires_rationale():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_repo(repo)
        root = repo / "experiments"
        (root / "G1").mkdir(parents=True)
        (root / "G2").mkdir(parents=True)
        (repo / "x").write_text("x")
        _run(["git", "add", "."], repo)
        _run(["git", "commit", "-q", "-m", "init"], repo)

        cwd0 = os.getcwd(); os.chdir(repo)
        try:
            PR.lock_prereg("G1", {"corr_min": 0.9}, experiments_root=root)
            try:
                PR.lock_prereg("G2", {"corr_min": 0.85}, experiments_root=root)
            except PR.PreregError as exc:
                assert "finding #9" in str(exc)
                print("  [ok] loosened threshold w/o rationale rejected (finding #9)")
            else:
                raise AssertionError("expected PreregError for silent threshold change")

            PR.lock_prereg(
                "G2",
                {"corr_min": 0.85},
                {"corr_min": "affine world has higher irreducible noise; see spec §R3"},
                experiments_root=root,
            )
            print("  [ok] loosened threshold WITH rationale allowed")
        finally:
            os.chdir(cwd0)


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
