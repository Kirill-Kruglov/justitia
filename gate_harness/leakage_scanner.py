"""AST-based fit-path leakage scanner.

Fixes audit findings:
  #3  leakage_audit fields were hardcoded self-reports, not computations; a real
      variant->classifier leak passed the audit because the audit never inspected
      the classifier source.
  #4  variant_oracle_audit.run_b2_passes_variant_to_classifier hardcoded False.
  #6  ground-truth (truth_axes=3) entering a decision path via evaluation.

This scanner does NOT self-report. Every field it emits is either backed by an
actual AST finding with a file+line, or is explicitly marked NOT_VERIFIABLE — in
which case the corresponding gate check is FAIL (never silently skipped).

Why AST and not grep or ``pattern in source``: the Ascesis toy worlds read truth
through dict *string keys* — ``record["z_obj"]`` — not through identifiers. A
scan that only walks ``ast.Name`` would miss the exact leakage class the audit
found. This scanner therefore inspects, for every fit-path function:

  (a) parameter names,
  (b) identifier reads          (ast.Name),
  (c) attribute access          (ast.Attribute, e.g. record.z_obj),
  (d) string subscript keys     (record["z_obj"], obj["variant"]),
  (e) any string constant       (catches "product3d"-style variant branching),
  (f) free variables / closures (co_freevars, __closure__),
  (g) referenced module globals (co_names ∩ __globals__ ∩ forbidden).

A forbidden name appearing under any of (a)-(g) is a CONFIRMED leak.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from typing import Any, Callable, Iterable


# Base forbidden set every gate inherits. Per-gate scans MUST include these and
# may extend them; they may never shrink the base set (enforced in scan()).
BASE_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "z_obj",
        "true_z",
        "true_bias",
        "true_dimension",
        "true_coordinates",
        "true_relation",
        "ground_truth",
        "variant",
        "generator_type",
        "generator",
        "truth_axes",
        "x_value",
        "y_value",
        "z_value",
        "dimension_label",
        "expected_classification",
        "result_by_variant",
        "seed_to_result",
        "status_by_seed",
    }
)


class LeakageError(RuntimeError):
    pass


def _forbidden_hits_in_source(fn: Callable, forbidden: frozenset[str]) -> list[dict[str, Any]]:
    """Return every AST-level occurrence of a forbidden name inside ``fn``."""
    try:
        raw = inspect.getsource(fn)
        base_line = inspect.getsourcelines(fn)[1]
        source_file = inspect.getsourcefile(fn) or "<unknown>"
    except (OSError, TypeError) as exc:  # pragma: no cover - defensive
        raise LeakageError(
            f"cannot read source of {getattr(fn, '__name__', fn)!r}: {exc}; "
            f"a function whose source cannot be inspected is NOT_VERIFIABLE -> FAIL"
        ) from exc

    tree = ast.parse(textwrap.dedent(raw))
    hits: list[dict[str, Any]] = []

    def record(name: str, node: ast.AST, kind: str) -> None:
        if name in forbidden:
            lineno = getattr(node, "lineno", 1)
            hits.append(
                {
                    "forbidden_name": name,
                    "access_kind": kind,
                    "file": source_file,
                    "line": base_line + lineno - 1,
                }
            )

    for node in ast.walk(tree):
        # (a) parameter names
        if isinstance(node, ast.arg):
            record(node.arg, node, "parameter")
        # (b) identifier reads/writes
        elif isinstance(node, ast.Name):
            record(node.id, node, "identifier")
        # (c) attribute access: record.z_obj
        elif isinstance(node, ast.Attribute):
            record(node.attr, node, "attribute")
        # (d)/(e) string constants, incl. dict-string-key subscripts
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            record(node.value, node, "string_constant")

    # (f) closures / free variables
    for freevar in getattr(fn.__code__, "co_freevars", ()):  # type: ignore[attr-defined]
        if freevar in forbidden:
            hits.append(
                {
                    "forbidden_name": freevar,
                    "access_kind": "closure_freevar",
                    "file": source_file,
                    "line": base_line,
                }
            )

    # (g) referenced module globals that are forbidden
    referenced = set(getattr(fn.__code__, "co_names", ()))  # type: ignore[attr-defined]
    for name in referenced & forbidden:
        if name in getattr(fn, "__globals__", {}):
            hits.append(
                {
                    "forbidden_name": name,
                    "access_kind": "module_global",
                    "file": source_file,
                    "line": base_line,
                }
            )
    return hits


def scan_audit_report_integrity(audit_fn: Callable) -> dict[str, Any]:
    """Detect audit functions that return hardcoded self-reports (finding #3).

    An audit field whose returned value is a literal constant (e.g.
    ``"learner_fit_reads_true_z_obj": False``) proves nothing — it is a claim,
    not a check. This scanner parses the audit function's returned dict(s) and
    marks every constant-valued field ``NOT_VERIFIABLE``; any such field fails
    the overall verdict. Fields whose value is a computed expression (call,
    comparison, name, subscript, boolean op, ...) are ``ast_scan``.
    """
    try:
        raw = inspect.getsource(audit_fn)
        base_line = inspect.getsourcelines(audit_fn)[1]
        source_file = inspect.getsourcefile(audit_fn) or "<unknown>"
    except (OSError, TypeError) as exc:  # pragma: no cover - defensive
        return {
            "computed_by": "NOT_VERIFIABLE",
            "reason": f"cannot read source of audit function: {exc}",
            "passed": False,
        }

    tree = ast.parse(textwrap.dedent(raw))
    fields: dict[str, Any] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)):
            continue
        for key_node, val_node in zip(node.value.keys, node.value.values):
            if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
                continue  # dynamic keys handled conservatively below
            key = key_node.value
            if isinstance(val_node, ast.Constant):
                fields[key] = {
                    "computed_by": "NOT_VERIFIABLE",
                    "reason": "hardcoded literal, not a computation",
                    "literal_value": val_node.value,
                    "line": base_line + getattr(val_node, "lineno", 1) - 1,
                }
            else:
                fields[key] = {
                    "computed_by": "ast_scan",
                    "expr_type": type(val_node).__name__,
                    "line": base_line + getattr(val_node, "lineno", 1) - 1,
                }

    # A dict built dynamically (no literal Return dict found) cannot be verified
    # field-by-field statically -> fail closed.
    if not fields:
        return {
            "computed_by": "NOT_VERIFIABLE",
            "reason": "no literal return-dict found to verify field-by-field",
            "file": source_file,
            "passed": False,
        }

    passed = all(v["computed_by"] == "ast_scan" for v in fields.values())
    return {
        "computed_by": "ast_scan",
        "file": source_file,
        "fields": fields,
        "not_verifiable_fields": sorted(
            k for k, v in fields.items() if v["computed_by"] == "NOT_VERIFIABLE"
        ),
        "passed": passed,
    }


def scan_fit_path(
    fit_path_functions: Iterable[Callable],
    forbidden_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Scan every fit/predict/classify function for forbidden (truth) names.

    ``forbidden_names`` extends (never replaces) ``BASE_FORBIDDEN_NAMES``.
    Returns an audit dict where each function's verdict is backed by AST
    evidence or is NOT_VERIFIABLE (-> the whole scan FAILs).
    """
    forbidden = BASE_FORBIDDEN_NAMES | frozenset(forbidden_names)
    functions = list(fit_path_functions)
    if not functions:
        # Fail closed: an empty fit-path registry cannot be trusted to be clean.
        return {
            "computed_by": "NOT_VERIFIABLE",
            "reason": "no fit-path functions registered to scan",
            "passed": False,
        }

    per_function: dict[str, Any] = {}
    all_hits: list[dict[str, Any]] = []
    not_verifiable = False
    for fn in functions:
        name = getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
        try:
            hits = _forbidden_hits_in_source(fn, forbidden)
        except LeakageError as exc:
            per_function[name] = {"computed_by": "NOT_VERIFIABLE", "reason": str(exc)}
            not_verifiable = True
            continue
        per_function[name] = {
            "computed_by": "ast_scan",
            "leak_detected": bool(hits),
            "evidence": hits,
        }
        all_hits.extend(hits)

    passed = (not all_hits) and (not not_verifiable)
    return {
        "computed_by": "ast_scan",
        "forbidden_names": sorted(forbidden),
        "fit_path_functions_scanned": [
            getattr(fn, "__qualname__", getattr(fn, "__name__", repr(fn)))
            for fn in functions
        ],
        "per_function": per_function,
        "leak_hits": all_hits,
        "not_verifiable_present": not_verifiable,
        "passed": passed,
    }


def assert_no_fit_path_leakage(
    fit_path_functions: Iterable[Callable],
    forbidden_names: Iterable[str] = (),
) -> dict[str, Any]:
    """Runner entrypoint: raise LeakageError unless the scan passes cleanly."""
    report = scan_fit_path(fit_path_functions, forbidden_names)
    if not report.get("passed"):
        raise LeakageError(
            "fit-path leakage scan did not pass:\n"
            + "\n".join(
                f"  {h['forbidden_name']} via {h['access_kind']} "
                f"@ {h['file']}:{h['line']}"
                for h in report.get("leak_hits", [])
            )
            + ("\n  (some functions were NOT_VERIFIABLE)" if report.get("not_verifiable_present") else "")
        )
    return report
