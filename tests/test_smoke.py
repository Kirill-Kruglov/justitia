"""End-to-end smoke: the full pipeline runs and its integrity gates pass."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_smoke_pipeline_runs_and_integrity_passes():
    proc = subprocess.run(
        [sys.executable, "run.py", "--smoke"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    # the runtime gates (blindness / selection / decoupling) a coarse pass can evaluate
    assert "smoke: integrity checks PASS (7/7)." in proc.stdout
