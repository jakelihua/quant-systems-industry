"""Synthetic regression, time-split scoring, and drift monitoring."""
import json
import math
import random
from pathlib import Path


def sample():
    rng = random.Random(20261122)
    rows = []
    for i in range(420):
        x = rng.gauss(0 if i < 360 else 1.3, 1)
        strength = .003 if i < 360 else -.002
        y = strength*x + rng.gauss(0, .002)
        rows.append((i, x, y))
    return rows


def fit_linear(train):
    xs = [x for _, x, _ in train]
    ys = [y for _, _, y in train]
    x0, y0 = math.fsum(xs)/len(xs), math.fsum(ys)/len(ys)
    slope = math.fsum((x-x0)*(y-y0) for x, y in zip(xs, ys))/math.fsum((x-x0)**2 for x in xs)
    return y0-slope*x0, slope


def evaluate(rows, model):
    intercept, slope = model
    predictions = [intercept + slope*x for _, x, _ in rows]
    realized = [y for _, _, y in rows]
    rmse = math.sqrt(math.fsum((p-y)**2 for p, y in zip(predictions, realized))/len(rows))
    rmse_zero = math.sqrt(math.fsum(y*y for y in realized)/len(rows))
    correct = sum((p > 0) == (y > 0) for p, y in zip(predictions, realized))/len(rows)
    return {"range": [rows[0][0], rows[-1][0]], "rmse": rmse, "zero_forecast_rmse": rmse_zero,
            "directional_accuracy": correct}


def score():
    rows = sample()
    train, stable, shifted = rows[:300], rows[300:360], rows[360:]
    model = fit_linear(train)
    train_mean = math.fsum(r[1] for r in train)/len(train)
    train_sd = math.sqrt(math.fsum((r[1]-train_mean)**2 for r in train)/len(train))
    windows = {}
    for name, block in (("stable_validation", stable), ("shifted_forward", shifted)):
        z = (math.fsum(r[1] for r in block)/len(block)-train_mean)/train_sd
        windows[name] = {**evaluate(block, model), "feature_mean_shift_train_sd": z,
                         "feature_shift_alert": abs(z) > .75}
    return {"data_provenance": "synthetic; known regime and feature shift", "train_range": [0,299],
            "coefficients": list(model), **windows}


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "out"
    out.mkdir(exist_ok=True)
    result = score()
    (out / "model-drift.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(result)
