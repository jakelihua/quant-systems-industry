"""Synthetic index portfolio construction and post-trade reconciliation."""
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = (30, 20, 25, 25)
PREVIOUS = (25, 25, 25, 25)
ALPHA_BPS = (300, -100, 150, 0)
LOADINGS = (1.15, .85, 1.05, .95)
IDIO_ANNUAL_VOL = (.19, .17, .21, .16)


def diagnostics(weights):
    active = [(w-b)/100 for w, b in zip(weights, BENCHMARK)]
    market_beta = math.fsum(a * beta for a, beta in zip(active, LOADINGS))
    variance = (.18 * market_beta)**2 + math.fsum((a * v)**2 for a, v in zip(active, IDIO_ANNUAL_VOL))
    turnover = sum(abs(w-old) for w, old in zip(weights, PREVIOUS))/100
    alpha = math.fsum(a * score for a, score in zip(active, ALPHA_BPS))
    return {"weights_percent": list(weights), "forecast_active_return_bps": alpha,
            "active_beta": market_beta, "active_industry_1": active[0]+active[1],
            "annual_tracking_error": math.sqrt(variance), "two_sided_turnover": turnover,
            "turnover_cost_bps": 15 * turnover,
            "objective_score": alpha - 15*turnover - 20_000*variance}


def search_portfolios():
    combinations = (weights for weights in itertools.product(range(0, 41, 5), repeat=4)
                    if sum(weights) == 100)
    rows = [diagnostics(weights) for weights in combinations]
    valid = [row for row in rows if abs(row["active_industry_1"]) <= .0500001
             and abs(row["active_beta"]) <= .0400001 and row["annual_tracking_error"] <= .04
             and row["two_sided_turnover"] <= .3000001]
    choose = lambda row: (row["objective_score"], tuple(row["weights_percent"]))
    return {"candidates": len(rows), "feasible": len(valid), "benchmark": diagnostics(BENCHMARK),
            "budget_and_position_cap_only": max(rows, key=choose), "fully_constrained": max(valid, key=choose)}


def reconcile(local, external):
    def index(rows):
        values, duplicates = {}, set()
        for key, symbol, side, qty, price in rows:
            if key in values:
                duplicates.add(key)
            values.setdefault(key, (symbol, side, qty, price))
        return values, sorted(duplicates)
    left, d_left = index(local)
    right, d_right = index(external)
    return {"local_duplicates": d_left, "external_duplicates": d_right,
            "missing_locally": sorted(right.keys()-left.keys()),
            "missing_externally": sorted(left.keys()-right.keys()),
            "field_mismatches": sorted(key for key in left.keys() & right.keys() if left[key] != right[key])}


def main():
    local = [("X1", "ETF-X", "buy", 60, 501), ("X2", "ETF-X", "sell", 10, 504),
             ("X2", "ETF-X", "sell", 10, 504), ("X4", "ETF-X", "buy", 10, 502)]
    external = [("X1", "ETF-X", "buy", 60, 501), ("X2", "ETF-X", "sell", 10, 503),
                ("X3", "ETF-Y", "buy", 15, 605)]
    result = {"data_provenance": "synthetic", "portfolio": search_portfolios(),
              "reconciliation": reconcile(local, external)}
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "portfolio-controls.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
