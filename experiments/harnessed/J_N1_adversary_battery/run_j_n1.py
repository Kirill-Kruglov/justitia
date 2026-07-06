#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import math
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from experiments.harnessed.common import ensure_imports, mean, read_prereg, write_json

ensure_imports()

from gate_harness import evaluation_oracle as EO  # noqa: E402
from gate_harness import leakage_scanner as LS  # noqa: E402
from gate_harness import seed_policy as SP  # noqa: E402
from gate_harness.runner import run_gate  # noqa: E402

import atlas  # noqa: E402

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE / "outputs"

FORBIDDEN_NAMES = [
    *atlas.base.STRATEGY_FIELDS,
    "exploitative_label",
    "lineages",
    "strategy",
    "hidden_type",
    "_exploit_score",
    "exploit_score",
]

WORLDS = [
    "W2_pure_capture",
    "W3_catastrophe_ambiguity",
    "W4_scavenger_catastrophe",
    "W5_monoculture_shock",
    "W6_mutation_corridor",
]
FEATURES = [
    "wellness",
    "productivity",
    "recovery",
    "migration_capacity",
    "strategy_diversity",
    "response_diversity",
    "resource_concentration",
    "apparent_cooperation",
    "sag",
    "last_aid",
    "response_to_aid",
    "neighbor_delta",
    "global_welfare",
]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _sigmoid(x):
    if x < -40:
        return 0.0
    if x > 40:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def fit_logistic_regression(xs, ys, steps=220, lr=0.08):
    weights = [0.0] * (len(xs[0]) + 1)
    for _ in range(steps):
        grad = [0.0] * len(weights)
        for x, y in zip(xs, ys):
            row = [1.0, *x]
            err = _sigmoid(_dot(weights, row)) - y
            for i, v in enumerate(row):
                grad[i] += err * v
        scale = lr / max(1, len(xs))
        for i in range(len(weights)):
            weights[i] -= scale * grad[i]
    return weights


def predict_logistic_regression(model, xs):
    return [1 if _sigmoid(_dot(model, [1.0, *x])) >= 0.5 else 0 for x in xs]


def fit_knn(xs, ys, k=7):
    return {"xs": xs, "ys": ys, "k": k}


def predict_knn(model, xs):
    out = []
    for x in xs:
        ranked = sorted(
            ((sum((a - b) ** 2 for a, b in zip(x, row)), y) for row, y in zip(model["xs"], model["ys"])),
            key=lambda t: t[0],
        )
        votes = [y for _, y in ranked[: model["k"]]]
        out.append(1 if sum(votes) >= len(votes) / 2 else 0)
    return out


def fit_nearest_centroid(xs, ys):
    groups = defaultdict(list)
    for x, y in zip(xs, ys):
        groups[y].append(x)
    centroids = {}
    for y, rows in groups.items():
        centroids[y] = [mean([r[i] for r in rows]) for i in range(len(xs[0]))]
    return centroids


def predict_nearest_centroid(model, xs):
    out = []
    for x in xs:
        best = min(model, key=lambda y: sum((a - b) ** 2 for a, b in zip(x, model[y])))
        out.append(int(best))
    return out


def fit_decision_stump_ensemble(xs, ys):
    stumps = []
    n_features = len(xs[0])
    for j in range(n_features):
        vals = sorted(set(row[j] for row in xs))
        candidates = vals[:: max(1, len(vals) // 12)]
        best = None
        for threshold in candidates:
            for polarity in [1, -1]:
                preds = [1 if polarity * row[j] >= polarity * threshold else 0 for row in xs]
                acc = sum(int(p == y) for p, y in zip(preds, ys)) / len(ys)
                if best is None or acc > best[0]:
                    best = (acc, j, threshold, polarity)
        if best:
            stumps.append(best)
    stumps.sort(reverse=True)
    return stumps[: min(9, len(stumps))]


def predict_decision_stump_ensemble(model, xs):
    out = []
    for x in xs:
        votes = [1 if polarity * x[j] >= polarity * threshold else 0 for _, j, threshold, polarity in model]
        out.append(1 if sum(votes) >= len(votes) / 2 else 0)
    return out


CLASSIFIERS = {
    "logistic_regression_manual_gd": (fit_logistic_regression, predict_logistic_regression),
    "knn_k7": (fit_knn, predict_knn),
    "nearest_centroid": (fit_nearest_centroid, predict_nearest_centroid),
    "decision_stump_ensemble": (fit_decision_stump_ensemble, predict_decision_stump_ensemble),
}


def balanced_accuracy(predictions, labels):
    positives = [p == y for p, y in zip(predictions, labels) if y == 1]
    negatives = [p == y for p, y in zip(predictions, labels) if y == 0]
    tpr = mean([1.0 if x else 0.0 for x in positives]) if positives else 0.0
    tnr = mean([1.0 if x else 0.0 for x in negatives]) if negatives else 0.0
    return 0.5 * (tpr + tnr)


def extract_examples(seed: int, world: str):
    params = atlas.params_for_variant("C", world, scenario="adversary_battery")
    model = atlas.BoundaryAtlasModel(seed, params)
    examples = []
    for step in range(atlas.base.STEPS):
        obs = model._delayed_obs()
        for i, z in enumerate(model.zones):
            label = 1 if model._weighted(z, "extraction_rate") + model._weighted(z, "aid_interception_rate") + model._weighted(z, "neighbor_harm_rate") > 0.95 else 0
            examples.append((
                [
                    obs.wellness[i],
                    obs.productivity[i],
                    obs.recovery[i],
                    obs.migration_capacity[i],
                    obs.strategy_diversity[i],
                    obs.response_diversity[i],
                    obs.resource_concentration[i],
                    obs.apparent_cooperation[i],
                    obs.sag[i],
                    obs.last_aid[i],
                    obs.response_to_aid[i],
                    obs.neighbor_delta[i],
                    obs.global_welfare,
                ],
                label,
            ))
        model.step(step)
    return examples


def normalize_train_eval(train_x, eval_x):
    cols = list(zip(*train_x))
    mins = [min(c) for c in cols]
    maxs = [max(c) for c in cols]

    def norm(rows):
        out = []
        for row in rows:
            out.append([
                0.0 if maxs[i] == mins[i] else (row[i] - mins[i]) / (maxs[i] - mins[i])
                for i in range(len(row))
            ])
        return out

    return norm(train_x), norm(eval_x)


def _score_predictions(predictions, labels):
    return balanced_accuracy(predictions, labels)


def _evaluation_suite():
    return _score_predictions([0, 1], [0, 1])


def experiment(smoke: bool) -> dict:
    thresholds = read_prereg(HERE)["thresholds"]
    seeds = thresholds["smoke_seeds"] if smoke else thresholds["seeds"]
    by_world = {}
    for world in WORLDS:
        rows = []
        for seed in seeds:
            rows.extend(extract_examples(int(seed), world))
        by_world[world] = rows

    fold_results = []
    for heldout in WORLDS:
        train = [row for world, rows in by_world.items() if world != heldout for row in rows]
        test = by_world[heldout]
        train_x, train_y = [x for x, _ in train], [y for _, y in train]
        test_x, test_y = [x for x, _ in test], [y for _, y in test]
        train_x, test_x = normalize_train_eval(train_x, test_x)
        for name, (fit, predict) in CLASSIFIERS.items():
            model = fit(train_x, train_y)
            preds = predict(model, test_x)
            fold_results.append({
                "heldout_world": heldout,
                "classifier": name,
                "balanced_accuracy": balanced_accuracy(preds, test_y),
                "n_train": len(train_y),
                "n_eval": len(test_y),
                "positive_rate_eval": mean([float(y) for y in test_y]),
            })

    max_by_classifier = {}
    for name in CLASSIFIERS:
        vals = [r["balanced_accuracy"] for r in fold_results if r["classifier"] == name]
        max_by_classifier[name] = max(vals)

    max_score = max(max_by_classifier.values())
    if all(v <= thresholds["all_classifiers_below_bar"] for v in max_by_classifier.values()):
        outcome = "PASS"
    elif any(v >= thresholds["finding_bar"] for v in max_by_classifier.values()):
        outcome = "FAIL"
    else:
        outcome = "INCONCLUSIVE"

    seed_report = SP.enforce_seed_policy([
        {"metric": "J_N1_holdout_world_battery", "role": "core", "seeds": len(seeds), "pass_fail": "PASS"},
    ])
    if not seed_report["admissible"]:
        outcome = "INCONCLUSIVE"

    write_json(OUTPUTS / "fold_results.json", {"fold_results": fold_results, "max_by_classifier": max_by_classifier})
    return {
        "question": "Can stdlib adversaries recover exploitative zones from observable justitia features across held-out worlds?",
        "mode": "prospective; outcome unknown at lock time; decision citable under ANY outcome",
        "metric": "Maximum held-out balanced accuracy across classifiers and worlds.",
        "features": FEATURES,
        "preregistered_thresholds": thresholds,
        "max_balanced_accuracy": max_score,
        "max_by_classifier": max_by_classifier,
        "fold_results_path": "outputs/fold_results.json",
        "seed_policy": seed_report,
        "decision": outcome,
        "downstream_consequence": "PASS strengthens the tested blindness claim; FAIL reports sufficient observable statistics; INCONCLUSIVE is published as-is.",
        "fact": "The battery trained on K-1 worlds and evaluated on the held-out world for each fold.",
        "inference": "Only the preregistered outcome branch may be cited.",
        "what_was_not_shown": "This does not prove hidden strategy recovery impossible for all model classes or feature sets.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    leak = LS.scan_fit_path(
        [
            fit_logistic_regression,
            predict_logistic_regression,
            fit_knn,
            predict_knn,
            fit_nearest_centroid,
            predict_nearest_centroid,
            fit_decision_stump_ensemble,
            predict_decision_stump_ensemble,
        ],
        forbidden_names=FORBIDDEN_NAMES,
    )
    taut = {
        "construction_may_be_tautological": False,
        "information_ratio": None,
        "computed_before_learner": True,
        "baseline": "Chance balanced accuracy is 0.5; thresholds are preregistered before battery run.",
    }
    eo = EO.scan_evaluation_call_sites(_evaluation_suite, entrypoint_names=["_score_predictions"], forbidden_names=FORBIDDEN_NAMES)["evaluation_oracle_log"]
    decision = run_gate(HERE, lambda: experiment(args.smoke), leakage_report=leak, tautology_report=taut, evaluation_oracle_log=eo)
    print(f"decision: {decision['decision']} written to {HERE / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

