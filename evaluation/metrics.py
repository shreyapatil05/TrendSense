"""Dependency-free evaluation metrics."""
import math

def classification_metrics(actual, predicted, labels=None):
    labels = labels or sorted(set(actual) | set(predicted))
    matrix = {a: {p: 0 for p in labels} for a in labels}
    for a, p in zip(actual, predicted):
        if a in matrix and p in matrix[a]: matrix[a][p] += 1
    per_label = {}
    for label in labels:
        tp = matrix[label][label]
        fp = sum(matrix[a][label] for a in labels if a != label)
        fn = sum(matrix[label][p] for p in labels if p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    n = len(actual)
    return {"accuracy": sum(a == p for a, p in zip(actual, predicted)) / n if n else 0.0,
            "macro_f1": sum(x["f1"] for x in per_label.values()) / len(labels) if labels else 0.0,
            "balanced_accuracy": sum(x["recall"] for x in per_label.values()) / len(labels) if labels else 0.0,
            "per_label": per_label, "confusion_matrix": matrix}

def regression_metrics(actual, predicted):
    errors = [p - a for a, p in zip(actual, predicted)]
    if not errors: return {"mae": None, "rmse": None}
    return {"mae": sum(abs(e) for e in errors) / len(errors),
            "rmse": math.sqrt(sum(e * e for e in errors) / len(errors))}

def precision_at_k(actual_positive_ids, ranked_ids, k):
    chosen = ranked_ids[:k]
    return sum(x in set(actual_positive_ids) for x in chosen) / len(chosen) if chosen else 0.0
