"""Offline ETF experiment. Run from any directory with Python 3.9+."""
import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ETF = ("sh510300", "sh510500", "sh518880")
CALENDAR = "sh000001"
NAMES = {
    "momentum": "三 ETF 动量",
    "equal": "三 ETF 月度等权",
    "hs300": "沪深300ETF 持有",
    "gold": "黄金ETF 持有",
    "no_gold": "两只股票 ETF 动量",
}
WARMUP, START, SPLIT, END = "2015-07-01", "2016-01-04", "2023-01-03", "2025-12-31"
WINDOWS = (20, 60, 120)
COSTS = (0, 10, 25, 50)
BASE_COST = 10
EPSILON = 1e-11

def load_market(path):
    raw = path.read_bytes()
    batches = json.loads(raw)
    bars = {symbol: {} for symbol in (*ETF, CALENDAR)}
    overlaps = 0
    keys = set()
    calendar_ohlc_issues = []
    for batch in batches:
        symbol = batch["ticker"]
        key = batch["key"]
        if key != ("day" if symbol == CALENDAR else "qfqday"):
            raise ValueError(f"Price basis changed for {symbol}: {key}")
        batch_id = (symbol, batch["year"])
        if batch_id in keys:
            raise ValueError(f"Repeated batch {batch_id}")
        keys.add(batch_id)
        previous = ""
        for row in batch["rows"]:
            day = row[0]
            if date.fromisoformat(day).isoformat() != day or day <= previous:
                raise ValueError(f"Unordered or invalid date {symbol} {day}")
            previous = day
            opening, close, high, low, volume = map(float, row[1:6])
            values = (opening, close, high, low, volume)
            valid = all(math.isfinite(v) and v > 0 for v in values)
            valid = valid and low <= min(opening, close) <= max(opening, close) <= high
            if not valid:
                if symbol != CALENDAR:
                    raise ValueError(f"Invalid ETF bar {symbol} {day}: {row}")
                calendar_ohlc_issues.append(day)
            prior = bars[symbol].get(day)
            if prior is not None:
                overlaps += 1
                if prior != values:
                    raise ValueError(f"Overlapping rows disagree {symbol} {day}")
            bars[symbol][day] = values

    expected = {(symbol, year) for symbol in bars for year in range(2015, 2026)}
    if keys != expected:
        raise ValueError("Unexpected request coverage")
    all_dates = set(bars[CALENDAR])
    dates = sorted(day for day in all_dates if WARMUP <= day <= END)
    if not dates or dates[0] != WARMUP or dates[-1] != END or START not in dates or SPLIT not in dates:
        raise ValueError("Missing study boundary date")
    # Plausibility screen for missing rows in the calendar proxy itself.
    for year in range(2015, 2026):
        count = sum(day.startswith(str(year)) for day in all_dates)
        if not 235 <= count <= 250:
            raise ValueError(f"Unexpected calendar coverage in {year}: {count} days")
    gaps = {}
    large_moves = {}
    for symbol in ETF:
        missing = sorted(all_dates - bars[symbol].keys())
        extra = sorted(bars[symbol].keys() - all_dates)
        in_scope = [day for day in missing + extra if WARMUP <= day <= END]
        if in_scope:
            raise ValueError(f"Calendar mismatch for {symbol}: {in_scope}")
        gaps[symbol] = {"missing": missing, "extra": extra}
        close = [bars[symbol][d][1] for d in dates]
        large_moves[symbol] = [dates[i] for i in range(1, len(dates))
                               if abs(close[i] / close[i-1] - 1) > .15]
    quality = {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "request_batches": len(batches),
        "identical_overlaps": overlaps,
        "first_date": dates[0],
        "last_date": dates[-1],
        "aligned_sessions": len(dates),
        "calendar_ohlc_exceptions": sorted(set(calendar_ohlc_issues)),
        "calendar_gaps_all_snapshot": gaps,
        "moves_over_15pct_in_scope": large_moves,
        "calendar": "腾讯上证综指日期代理",
        "price_basis": "腾讯 ETF 前复权日线",
    }
    return dates, bars, quality

def check_secondary(bars, path):
    sample = json.loads(path.read_text(encoding="utf-8"))["data"]
    symbol = "sh" + sample["code"]
    mismatches, days = [], []
    for line in sample["klines"]:
        day, *fields = line.split(",")
        days.append(day)
        if bars[symbol].get(day, ())[:4] != tuple(map(float, fields[:4])):
            mismatches.append(day)
    if not days or mismatches:
        raise ValueError(f"Secondary OHLC audit failed: {mismatches}")
    return {"source": "东方财富前复权", "symbol": symbol, "dates": days, "ohlc_match": len(days)}


def choose_target(bars, dates, signal_index, lookback, universe):
    then, now = dates[signal_index - lookback], dates[signal_index]
    momentum = {s: bars[s][now][1] / bars[s][then][1] - 1 for s in universe}
    leader = min(momentum, key=lambda symbol: (-momentum[symbol], symbol))
    return ({leader: 1.0} if momentum[leader] > 0 else {}), momentum

def rebalance(current, cash, weights, fee):
    pre_nav = math.fsum(current.values()) + cash
    post_nav = pre_nav
    # Cost is charged on both buy and sell notionals. Resolve the post-fee budget.
    for _ in range(100):
        turnover = math.fsum(abs(weights.get(s, 0) * post_nav - current[s]) for s in ETF)
        updated = pre_nav - turnover * fee
        if abs(updated - post_nav) < EPSILON:
            post_nav = updated
            break
        post_nav = updated
    else:
        raise ArithmeticError("Post-fee portfolio budget did not converge")
    values = {s: weights.get(s, 0) * post_nav for s in ETF}
    changes = {s: values[s] - current[s] for s in ETF}
    cost = fee * math.fsum(abs(change) for change in changes.values())
    new_cash = cash - math.fsum(changes.values()) - cost
    if new_cash < -EPSILON or abs(post_nav + cost - pre_nav) > EPSILON:
        raise ArithmeticError("Rebalance failed cash and cost reconciliation")
    return values, max(0.0, new_cash), changes, cost

def simulate(dates, bars, method, lookback=60, bps=BASE_COST):
    if method not in NAMES or not 1 <= lookback <= dates.index(START) - 1 or not 0 <= bps <= 100:
        raise ValueError("Invalid experiment parameters")
    units = dict.fromkeys(ETF, 0.0)
    cash, last_nav = 1.0, 1.0
    timeline, orders, signals = [], [], []
    start_index = dates.index(START)
    for i in range(start_index, len(dates)):
        day, previous = dates[i], dates[i-1]
        trade_day = i == start_index or day[:7] != previous[:7]
        cost, turnover_rate = 0.0, 0.0
        active = trade_day and (method not in ("hs300", "gold") or not timeline)
        if active:
            momentum = {}
            if method in ("momentum", "no_gold"):
                universe = ETF if method == "momentum" else ETF[:2]
                weights, momentum = choose_target(bars, dates, i-1, lookback, universe)
            elif method == "equal":
                weights = dict.fromkeys(ETF, 1 / 3)
            else:
                weights = {ETF[0] if method == "hs300" else ETF[2]: 1.0}
            open_price = {s: bars[s][day][0] for s in ETF}
            current = {s: units[s] * open_price[s] for s in ETF}
            opening_nav = math.fsum(current.values()) + cash
            values, cash, changes, cost = rebalance(current, cash, weights, bps / 10000)
            units = {s: values[s] / open_price[s] for s in ETF}
            turnover_rate = math.fsum(abs(v) for v in changes.values()) / opening_nav
            for s, change in changes.items():
                if abs(change) > EPSILON:
                    orders.append({"signal_date": previous, "trade_date": day, "symbol": s,
                                   "side": "BUY" if change > 0 else "SELL",
                                   "adjusted_open": open_price[s], "notional": abs(change),
                                   "fee": abs(change) * bps / 10000, "pre_trade_nav": opening_nav})
            signals.append({"signal_date": previous, "trade_date": day,
                            "lookback_anchor": dates[i-1-lookback] if momentum else "",
                            **{f"momentum_{s[2:]}": momentum.get(s, "") for s in ETF},
                            **{f"weight_{s[2:]}": weights.get(s, 0.0) for s in ETF},
                            "cash_weight": 1 - sum(weights.values()),
                            "turnover": turnover_rate, "cost": cost})
        closing = {s: units[s] * bars[s][day][1] for s in ETF}
        nav = math.fsum(closing.values()) + cash
        if not math.isfinite(nav) or nav <= 0:
            raise ArithmeticError(f"Invalid NAV on {day}")
        timeline.append({"date": day, "nav": nav, "daily_return": nav / last_nav - 1,
                         "cash_weight": cash / nav, "turnover": turnover_rate, "cost": cost,
                         **{f"weight_{s[2:]}": closing[s] / nav for s in ETF}})
        last_nav = nav
    return timeline, orders, signals

def metrics(rows):
    starting_nav = rows[0]["nav"] / (1 + rows[0]["daily_return"])
    peak, largest = starting_nav, 0.0
    peak_day, trough_day, worst_peak = "区间起点", "区间起点", "区间起点"
    for row in rows:
        if row["nav"] >= peak:
            peak, peak_day = row["nav"], row["date"]
        drawdown = row["nav"] / peak - 1
        if drawdown < largest:
            largest, worst_peak, trough_day = drawdown, peak_day, row["date"]
    returns = [row["daily_return"] for row in rows]
    total = rows[-1]["nav"] / starting_nav - 1
    vol = statistics.stdev(returns)
    return {"sessions": len(rows), "total": total, "cagr": (1 + total)**(252 / len(rows)) - 1,
            "volatility": vol * math.sqrt(252),
            "sharpe": statistics.mean(returns) * math.sqrt(252) / vol if vol else None,
            "max_drawdown": largest, "peak": worst_peak, "trough": trough_day,
            "annual_turnover": sum(row["turnover"] for row in rows) * 252 / len(rows),
            "cash_days": sum(row["cash_weight"] > .999999 for row in rows),
            "daily_cost_total_nav_units": sum(row["cost"] for row in rows)}

def paired_bootstrap(strategy, benchmark, block=20, samples=1500):
    logs = [math.log1p(x["daily_return"]) - math.log1p(y["daily_return"])
            for x, y in zip(strategy, benchmark)]
    n = len(logs)
    if n != len(strategy) or n != len(benchmark) or any(
        x["date"] != y["date"] for x, y in zip(strategy, benchmark)
    ):
        raise ValueError("Bootstrap series must share the same dates")
    circular = logs + logs[:block]
    blocks = [sum(circular[i:i+block]) for i in range(n)]
    full, partial = divmod(n, block)
    rng = random.Random(42)
    draws = []
    for _ in range(samples):
        value = sum(blocks[rng.randrange(n)] for _ in range(full))
        if partial:
            i = rng.randrange(n)
            value += sum(circular[i:i+partial])
        draws.append(math.expm1(value * 252 / n))
    bounds = statistics.quantiles(draws, n=40, method="inclusive")
    return {"relative_annualized": math.expm1(sum(logs) * 252 / n),
            "lower": bounds[0], "upper": bounds[-1], "block": block, "samples": samples}

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def period_rows(rows, period):
    if period == "holdout":
        return [r for r in rows if r["date"] >= SPLIT]
    if period == "development":
        return [r for r in rows if r["date"] < SPLIT]
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/tencent_snapshot.json")
    parser.add_argument("--secondary", type=Path, default=ROOT / "data/eastmoney_510300_20251224_20251231.json")
    parser.add_argument("--out", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    dates, bars, quality = load_market(args.snapshot)
    quality["secondary_audit"] = check_secondary(bars, args.secondary)
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out
    (output / "quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    all_runs = {method: simulate(dates, bars, method) for method in NAMES}
    scores, annual, curves, sensitivity = [], [], [], []
    for method, (rows, orders, signals) in all_runs.items():
        for period in ("all", "development", "holdout"):
            scores.append({"method": method, "period": period, **metrics(period_rows(rows, period))})
        for year in range(2016, 2026):
            subset = [r for r in rows if r["date"].startswith(str(year))]
            annual.append({"method": method, "year": year, **metrics(subset)})
        peak = 1.0
        for row in rows:
            peak = max(peak, row["nav"])
            curves.append({"method": method, **row, "drawdown": row["nav"] / peak - 1})
        if method == "momentum":
            write_csv(output / "signals.csv", signals)
            write_csv(output / "orders.csv", orders)
    for window in WINDOWS:
        for bps in COSTS:
            rows, _, _ = simulate(dates, bars, "momentum", window, bps)
            for period in ("all", "development", "holdout"):
                sensitivity.append({"lookback": window, "bps": bps, "period": period,
                                    **metrics(period_rows(rows, period))})
    rows, orders, signals = all_runs["momentum"]
    cash_days = Counter("cash" if r["cash_weight"] > .999999 else
                        max(ETF, key=lambda s: r[f"weight_{s[2:]}"]) for r in rows)
    checks = {"signal_count": len(signals), "order_count": len(orders),
              "total_fee_in_initial_nav_units": sum(r["fee"] for r in orders),
              "holding_sessions": dict(cash_days),
              "holdout_bootstrap": paired_bootstrap(period_rows(rows, "holdout"),
                                                    period_rows(all_runs["equal"][0], "holdout"))}
    for name, table in (("daily", curves), ("metrics", scores), ("annual", annual), ("sensitivity", sensitivity)):
        write_csv(output / (name + ".csv"), table)
    (output / "summary.json").write_text(json.dumps(
        {"metrics": scores, "annual": annual, "sensitivity": sensitivity, "checks": checks},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} trading sessions, {len(signals)} signals, {len(orders)} orders")
    for score in scores:
        if score["period"] in ("all", "holdout"):
            print(f"{score['period']:7} {score['method']:9} CAGR {score['cagr']:7.2%} "
                  f"MDD {score['max_drawdown']:7.2%} Sharpe {score['sharpe']:5.2f}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
