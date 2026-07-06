from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "model"
HARNESS_ROOT = ROOT / "experiments" / "harnessed"


def ensure_imports() -> None:
    for path in (ROOT, MODEL):
        s = str(path)
        if s not in sys.path:
            sys.path.insert(0, s)


def read_prereg(gate_dir: Path) -> dict[str, Any]:
    return json.loads((gate_dir / "PREREG.json").read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(value: Any) -> float:
    if value in ("", None):
        return math.nan
    return float(value)


def run_command(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, env=merged_env)
    return {
        "args": args,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
    }


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
