"""Standalone PNGs for selected-window, holdout and prospective comparisons."""
from pathlib import Path
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from evaluation.metrics import classification_metrics, regression_metrics


LABELS = ["UP", "STABLE", "DOWN"]


def _held_out_metrics(predictions):
    """Recompute every test metric from the exact rows used for plotting."""
    by_model = {}
    if not predictions:
        return by_model

    frame = pd.DataFrame(predictions)
    required = {
        "model", "actual_direction", "predicted_direction",
        "actual_interest", "predicted_interest",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Held-out predictions are missing columns: {sorted(missing)}")

    for model, rows in frame.groupby("model", sort=False):
        actual = rows["actual_direction"].astype(str).tolist()
        predicted = rows["predicted_direction"].astype(str).tolist()
        classification = classification_metrics(actual, predicted, LABELS)
        regression = regression_metrics(
            pd.to_numeric(rows["actual_interest"], errors="raise").tolist(),
            pd.to_numeric(rows["predicted_interest"], errors="raise").tolist(),
        )

        # A confusion matrix, accuracy and macro-F1 must describe one sample set.
        matrix_total = sum(
            classification["confusion_matrix"][actual_label][predicted_label]
            for actual_label in LABELS
            for predicted_label in LABELS
        )
        if matrix_total != len(rows):
            raise RuntimeError(
                f"Metric consistency failure for {model}: "
                f"matrix={matrix_total}, predictions={len(rows)}"
            )
        by_model[str(model)] = {
            "classification": classification,
            "regression": regression,
            "rows": int(len(rows)),
        }
    return by_model


def plot_experiment(window, report, predictions, directory, forecasts=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    plt.close("all")
    keys = list(window.keyword.unique())
    files = []
    held_out = _held_out_metrics(predictions)

    # Write the important evaluation artifacts first. Large keyword selections
    # may create dozens of detailed charts afterwards.
    names = list(report["models"])
    metric_rows = []
    for name in names:
        validation = report["models"][name].get("validation", {})
        test = held_out.get(name, report["models"][name].get("test", {}))
        classification = test.get("classification", {})
        regression = test.get("regression", {})
        metric_rows.append({
            "model": name,
            "validation_macro_f1": validation.get("classification", {}).get("macro_f1"),
            "validation_mae": validation.get("regression", {}).get("mae"),
            "test_rows": test.get("rows"),
            "test_accuracy": classification.get("accuracy"),
            "test_balanced_accuracy": classification.get("balanced_accuracy"),
            "test_macro_f1": classification.get("macro_f1"),
            "test_mae": regression.get("mae"),
            "test_rmse": regression.get("rmse"),
        })
    pd.DataFrame(metric_rows).to_csv(directory / "model_metrics.csv", index=False)

    fig, ax = plt.subplots(figsize=(10, 4))
    positions = np.arange(len(names))
    validation_f1 = [report["models"][n]["validation"]["classification"]["macro_f1"] for n in names]
    test_f1 = [held_out.get(n, report["models"][n].get("test", {})).get(
        "classification", {}).get("macro_f1", np.nan) for n in names]
    ax.bar(positions - .2, validation_f1, width=.4, label="Validation")
    ax.bar(positions + .2, test_f1, width=.4, label="Held-out test")
    ax.set_xticks(positions, names)
    ax.set_ylabel("Macro-F1"); ax.set_ylim(0, 1); ax.tick_params(axis="x", labelrotation=25); ax.legend()
    fig.tight_layout(); fig.savefig(directory / "model_comparison.png", dpi=130); plt.close("all")

    chosen = held_out.get(
        report["classifier"],
        report["models"][report["classifier"]].get("test", {}),
    )
    if "classification" in chosen:
        labels = LABELS
        cm = chosen["classification"]["confusion_matrix"]
        matrix = np.array([[cm[a][b] for b in labels] for a in labels])
        fig, ax = plt.subplots(figsize=(6.4, 4.8))
        ax.imshow(matrix, cmap="Blues")
        for i in range(3):
            for j in range(3):
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center")
        ax.set_xticks(range(3), labels); ax.set_yticks(range(3), labels)
        score = chosen["classification"]["macro_f1"]
        accuracy = chosen["classification"]["accuracy"]
        ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
        ax.set_title(
            f"Held-out: {report['classifier']} "
            f"(n={chosen['rows']}, accuracy={accuracy:.3f}, macro-F1={score:.3f})"
        )
        fig.tight_layout(); fig.savefig(directory / "confusion_matrix.png", dpi=130); plt.close("all")
    # Pages of small multiples remain readable for 10, 20, 30 or more keywords.
    for page in range(0, len(keys), 6):
        selected = keys[page:page+6]
        fig, axes = plt.subplots(len(selected), 1, figsize=(11, 2.6 * len(selected)), squeeze=False)
        for ax, keyword in zip(axes[:, 0], selected):
            g = window[window.keyword == keyword]
            ax.plot(g.date, g.interest, label="Observed interest", color="navy")
            ax.axvline(pd.Timestamp(report["test_start"]), color="gray", linestyle=":", label="Test starts")
            ax.set_title(keyword)
            ax.set_ylabel("Request index")
            for item in forecasts or []:
                if item["keyword"] == keyword and item.get("predicted_interest") is not None:
                    ax.scatter(pd.Timestamp(item["target_date"]), item["predicted_interest"], marker="x", color="red", label="Future target prediction")
            ax.legend(loc="upper left", fontsize=8)
            ax.grid(alpha=.2)
        fig.autofmt_xdate(); fig.tight_layout()
        path = directory / f"selected_window_{page//6+1}.png"
        fig.savefig(path, dpi=130); plt.close("all"); files.append(str(path))
    if predictions:
        frame = pd.DataFrame(predictions)
        frame["target_date"] = pd.to_datetime(frame.target_date, utc=True)
        for keyword in keys:
            if not ((frame.keyword == keyword) & (frame.model == report["regressor"])).any():
                continue
            fig, ax = plt.subplots(figsize=(10, 4))
            for name in dict.fromkeys([report["regressor"], "persistence"]):
                g = frame[(frame.keyword == keyword) & (frame.model == name)].sort_values("target_date")
                if g.empty:
                    continue
                ax.plot(g.target_date, g.predicted_interest, "--o", label=name)
                if name == report["regressor"]:
                    ax.plot(g.target_date, g.actual_interest, "-o", label="Actual")
            ax.set_title(f"Held-out targets: {keyword}"); ax.set_ylabel("Request index"); ax.legend(); ax.grid(alpha=.2)
            fig.autofmt_xdate(); fig.tight_layout()
            path = directory / ("test_" + re.sub(r"[^a-zA-Z0-9]+", "_", keyword) + ".png")
            fig.savefig(path, dpi=120); plt.close("all"); files.append(str(path))
    if forecasts:
        ready = [item for item in forecasts if item.get("watchlist_rank")]
        top = sorted(ready, key=lambda item: item["watchlist_rank"])[:15]
        if top:
            fig, ax = plt.subplots(figsize=(9, max(4, len(top) * .35)))
            labels = [item["keyword"] for item in reversed(top)]
            scores = [item.get("watchlist_score", 0.0) for item in reversed(top)]
            colors = [{"INVEST": "seagreen", "AVOID": "firebrick", "WAIT": "goldenrod"}.get(item.get("decision"), "gray")
                      for item in reversed(top)]
            ax.barh(labels, scores, color=colors)
            ax.set_xlim(0, 1); ax.set_xlabel("Model P(UP) score")
            ax.set_title("Top forecast watchlist")
            fig.tight_layout(); fig.savefig(directory / "watchlist.png", dpi=140); plt.close(fig)
    return files


def plot_live(records, directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    if not records:
        return
    fig, ax = plt.subplots(figsize=(6, 5))
    x = [r["actual_interest"] for r in records]; y = [r["predicted_interest"] for r in records]
    ax.scatter(x, y)
    low, high = min(x+y), max(x+y)
    ax.plot([low, high], [low, high], "--", color="gray")
    ax.set_xlabel("Actual (forecast reference scale)"); ax.set_ylabel("Predicted")
    ax.set_title("Future forecast verification")
    fig.tight_layout(); fig.savefig(directory / "live_actual_vs_predicted.png", dpi=140); plt.close(fig)
