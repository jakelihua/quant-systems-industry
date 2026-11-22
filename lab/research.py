"""Prequential parameter selection and risk diagnostics on the frozen ETF study."""
import json
import math
import statistics
from pathlib import Path

from baseline import backtest as bt

ROOT = Path(__file__).resolve().parents[1]
FIRST_FORWARD_YEAR = 2019


def by_year(rows, year):
    return [row for row in rows if row["date"].startswith(str(year))]


def select_windows(history):
    selections, evidence = {}, []
    for year in range(FIRST_FORWARD_YEAR, 2026):
        cutoff = str(year)
        scores = {
            window: bt.metrics([r for r in rows if r["date"][:4] < cutoff])["sharpe"]
            for window, rows in history.items()
        }
        window = min(scores, key=lambda w: (-scores[w], w))
        selections[year] = window
        evidence.append({"forward_year": year, "selected": window, "training_sharpe": scores,
                         "last_training_date": max(r["date"] for r in history[window]
                                                   if r["date"][:4] < cutoff)})
    return selections, evidence


def risk(strategy, benchmark):
    if [row["date"] for row in strategy] != [row["date"] for row in benchmark]:
        raise ValueError("Risk series dates differ")
    returns = [r["daily_return"] for r in strategy]
    active = [a["daily_return"] - b["daily_return"] for a, b in zip(strategy, benchmark)]
    # Define expected shortfall explicitly as the mean of the worst ceil(2.5% * N) days.
    losses = sorted((-value for value in returns), reverse=True)
    tail_count = math.ceil(.025 * len(losses))
    peak = strategy[0]["nav"] / (1 + returns[0])
    underwater = longest = 0
    for row in strategy:
        if row["nav"] >= peak:
            peak, underwater = row["nav"], 0
        else:
            underwater += 1
            longest = max(longest, underwater)
    joint = [r["daily_return"] for r in benchmark]
    x, y = statistics.mean(joint), statistics.mean(returns)
    beta = sum((a-x)*(b-y) for a, b in zip(joint, returns)) / sum((a-x)**2 for a in joint)
    tracking = statistics.stdev(active)
    shocks = {"equity_gap": [-.07, -.09, .01], "gold_gap": [-.01, -.015, -.08],
              "cross_asset_selloff": [-.05, -.07, -.06]}
    weights = [strategy[-1]["weight_" + symbol[2:]] for symbol in bt.ETF]
    return {"historical_var_97_5_daily_loss": losses[tail_count-1],
            "historical_es_97_5_daily_loss": statistics.mean(losses[:tail_count]),
            "tail_days": tail_count, "tracking_error_annual": tracking * math.sqrt(252),
            "information_ratio": statistics.mean(active) / tracking * math.sqrt(252) if tracking else None,
            "beta_vs_equal": beta, "longest_underwater_sessions": longest,
            "last_weights": dict(zip(bt.ETF, weights)),
            "instant_shock_at_last_weights": {
                name: sum(w * shock for w, shock in zip(weights, shockset))
                for name, shockset in shocks.items()
            },
            "instant_shock_assumptions": {name: dict(zip(bt.ETF, shockset))
                                          for name, shockset in shocks.items()}}


def main():
    dates, bars, provenance = bt.load_market(ROOT / "baseline/data/tencent_snapshot.json")
    audit = bt.check_secondary(bars, ROOT / "baseline/data/eastmoney_510300_20251224_20251231.json")
    history = {window: bt.simulate(dates, bars, "momentum", window)[0] for window in bt.WINDOWS}
    fixed = history[60]
    equal = bt.simulate(dates, bars, "equal")[0]
    schedule, selection = select_windows(history)
    adaptive = bt.simulate(dates, bars, "momentum", 60, annual_lookbacks=schedule)[0]
    rows = []
    for entry in selection:
        year = entry["forward_year"]
        rows.append({**entry, "adaptive": bt.metrics(by_year(adaptive, year)),
                     "fixed60": bt.metrics(by_year(fixed, year)), "equal": bt.metrics(by_year(equal, year))})
    forward = {name: [r for r in series if int(r["date"][:4]) >= FIRST_FORWARD_YEAR]
               for name, series in (("adaptive", adaptive), ("fixed60", fixed), ("equal", equal))}
    results = {"selection_rule": "Choose highest expanding-window net daily Sharpe, ties choose shortest window",
               "candidate_windows": list(bt.WINDOWS), "cost_bps_per_traded_side": bt.BASE_COST,
               "history": rows, "forward_summary": {name: bt.metrics(series) for name, series in forward.items()},
               "adaptive_risk_vs_equal": risk(forward["adaptive"], forward["equal"])}
    output = ROOT / "out"
    output.mkdir(exist_ok=True)
    (output / "research.json").write_text(json.dumps(results, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    provenance["secondary_audit"] = audit
    provenance["secondary_url"] = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.510300&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56&klt=101&fqt=1&beg=20251224&end=20251231"
    )
    (output / "input-provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+"\n",
                                                   encoding="utf-8")
    for name, result in results["forward_summary"].items():
        print(f"{name:8} forward CAGR {result['cagr']:.2%}, MDD {result['max_drawdown']:.2%}")
    return results


if __name__ == "__main__":
    main()
