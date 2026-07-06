"""Evaluation-oracle detection (recovered spec §1.4, fixes finding #6).

Finding #6: ground truth (``truth_axes=3``) entered a classification/decision
path through ``evaluate_coords`` — an evaluation-adjacent call site — even though
the classifier's own fit path was clean. The original audit missed it because it
only looked at the classifier.

Two scans, both reusing the AST engine that already caught ``record["z_obj"]``:

1. ``scan_non_entrypoints`` — every decision/classification function that is NOT a
   declared evaluation entrypoint is subject to the same forbidden-names fit-path
   scan (delegates to ``leakage_scanner``).

2. ``scan_evaluation_call_sites`` — walk the full module and, at every call to a
   declared entrypoint, look for ground-truth values passed as keyword args or
   dict-literal values. A literal constant at the call site (``truth_axes=3``) is
   flagged distinctly and more harshly than a value threaded from the generator:
   a literal means a human wrote the answer directly into the harness call.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any, Callable, Iterable

from .leakage_scanner import BASE_FORBIDDEN_NAMES, scan_fit_path


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def scan_non_entrypoints(
    functions: Iterable[Callable],
    entrypoint_functions: Iterable[Callable],
    forbidden_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Fit-path scan on every function that is NOT an evaluation entrypoint."""
    entry_ids = {id(f) for f in entrypoint_functions}
    non_entry = [f for f in functions if id(f) not in entry_ids]
    return scan_fit_path(non_entry, forbidden_names)


def scan_evaluation_call_sites(
    module_or_fn: Any,
    entrypoint_names: Iterable[str],
    forbidden_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Flag ground-truth hints passed to evaluation entrypoints at each call site."""
    forbidden = BASE_FORBIDDEN_NAMES | frozenset(forbidden_names)
    entrypoints = set(entrypoint_names)

    try:
        raw = inspect.getsource(module_or_fn)
        base_line = inspect.getsourcelines(module_or_fn)[1] if not inspect.ismodule(module_or_fn) else 1
        source_file = inspect.getsourcefile(module_or_fn) or "<unknown>"
    except (OSError, TypeError) as exc:  # pragma: no cover - defensive
        return {
            "computed_by": "NOT_VERIFIABLE",
            "reason": f"cannot read source: {exc}",
            "evaluation_oracle_log": [],
            "passed": False,
        }

    tree = ast.parse(textwrap.dedent(raw))
    log: list[dict[str, Any]] = []

    def add(entrypoint: str, name: str, node: ast.AST, value_node: ast.AST) -> None:
        if name not in forbidden:
            return
        is_literal = isinstance(value_node, ast.Constant)
        log.append(
            {
                "call_site": f"{source_file}:{base_line + getattr(node, 'lineno', 1) - 1}",
                "entrypoint": entrypoint,
                "hint_name": name,
                "hint_value": value_node.value if is_literal else None,
                "hint_value_is_literal_constant": is_literal,
                "harness_provided_ground_truth_hint": True,
            }
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        entrypoint = _call_name(node.func)
        if entrypoint not in entrypoints:
            continue
        # keyword hints: evaluate_coords(..., truth_axes=3)
        for kw in node.keywords:
            if kw.arg is not None:
                add(entrypoint, kw.arg, node, kw.value)
        # dict-literal hints: evaluate_coords(..., {"truth_axes": 3})
        for arg in node.args:
            if isinstance(arg, ast.Dict):
                for key_node, val_node in zip(arg.keys, arg.values):
                    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                        add(entrypoint, key_node.value, node, val_node)

    return {
        "computed_by": "ast_scan",
        "source_file": source_file,
        "entrypoints": sorted(entrypoints),
        "evaluation_oracle_log": log,
        "any_harness_hint": bool(log),
        "any_literal_hint": any(e["hint_value_is_literal_constant"] for e in log),
        "passed": not log,
    }
