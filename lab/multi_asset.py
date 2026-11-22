"""Auditable synthetic multi-asset labs. All market paths are invented."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def futures_roll():
    # Two long contracts; use settlement-to-settlement variation on each actual contract.
    lots, multiplier, deposit, fee_per_lot = 2, 10, 2400, 2
    initial_margin, maintenance = .12, .10
    prices = [(100, None), (103, 110), (101, 107), (None, 114)]
    cash, net_variation, fees = deposit, 0, 0
    opened = False
    held, prior = 0, 0
    deposits, rows = 0, []
    for day, quotes in enumerate(prices):
        pnl, fee, posted, roll_gap = 0, 0, 0, None
        if opened:
            pnl = (quotes[held] - prior) * lots * multiplier
        else:
            fee = lots * fee_per_lot
            opened = True
        if day == 2:
            roll_gap = quotes[1] - quotes[0]
            held = 1
            fee = 2 * lots * fee_per_lot
        prior = quotes[held]
        net_variation += pnl
        fees += fee
        cash += pnl - fee
        notional = lots * multiplier * prior
        # Explicit extra collateral stress on the final day; no change to trading P&L.
        initial = (.14 if day == 3 else initial_margin) * notional
        minimum = (.13 if day == 3 else maintenance) * notional
        # Simulate a separate large OTC collateral encumbrance in the final scenario.
        encumbered = 2300 if day == 3 else 0
        if cash - encumbered < minimum:
            posted = round(initial - (cash - encumbered), 2)
            cash += posted
            deposits += posted
        rows.append({"day": day, "contract": ("near", "far")[held], "settlement": prior,
                     "variation": pnl, "fees": fee, "roll_gap_points": roll_gap,
                     "maintenance": minimum, "cash": cash, "encumbered": encumbered,
                     "extra_collateral": posted})
    continuous_jump = (prices[-1][1] - prices[0][0]) * lots * multiplier
    return {"daily": rows, "sum_variation": net_variation, "naive_stitched_variation": continuous_jump,
            "fees": fees, "pnl_ex_collateral": net_variation - fees,
            "initial_deposit": deposit, "extra_collateral": deposits, "ending_cash": cash}


def normal_cdf(x):
    return .5 * (1 + math.erf(x / math.sqrt(2)))


def normal_pdf(x):
    return math.exp(-.5 * x * x) / math.sqrt(2 * math.pi)


def european(spot, strike, time, rate, dividend, sigma, kind):
    if min(spot, strike, time, sigma) <= 0 or kind not in ("call", "put"):
        raise ValueError("Unsupported option parameters")
    scale = sigma * math.sqrt(time)
    d1 = (math.log(spot/strike) + (rate-dividend+.5*sigma*sigma)*time)/scale
    d2 = d1 - scale
    s, k = spot*math.exp(-dividend*time), strike*math.exp(-rate*time)
    sign = 1 if kind == "call" else -1
    return {"price": sign*(s*normal_cdf(sign*d1)-k*normal_cdf(sign*d2)),
            "delta": sign*math.exp(-dividend*time)*normal_cdf(sign*d1),
            "gamma": math.exp(-dividend*time)*normal_pdf(d1)/(spot*scale),
            "vega_per_vol_point": s*normal_pdf(d1)*math.sqrt(time)/100}


def implied_vol(target, spot, strike, time, rate, dividend, kind):
    def price(sigma):
        return european(spot, strike, time, rate, dividend, sigma, kind)["price"]
    lo, hi = 1e-6, 5.0
    if not price(lo) <= target <= price(hi):
        raise ValueError("Quote outside IV solver price range")
    for _ in range(55):
        mid = (lo+hi)/2
        if price(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo+hi)/2


def options_stress():
    spot, time, rate, q, contract = 5.0, .25, .02, .01, 10_000
    positions = [(4.8, "put", 2, .26), (5.0, "call", -1, .22), (5.2, "call", -1, .23)]
    shock_spot, shock_iv = -.30, .08
    rows = []
    for strike, kind, quantity, vol in positions:
        base = european(spot, strike, time, rate, q, vol, kind)
        bid = european(spot, strike, time, rate, q, vol-.008, kind)["price"]
        ask = european(spot, strike, time, rate, q, vol+.008, kind)["price"]
        exact = european(spot+shock_spot, strike, time, rate, q, vol+shock_iv, kind)["price"]
        linear = base["delta"]*shock_spot + base["vega_per_vol_point"]*shock_iv*100
        second = linear + .5*base["gamma"]*shock_spot**2
        factor = quantity * contract
        rows.append({"strike": strike, "type": kind, "position_contracts": quantity,
                     "bid": bid, "ask": ask,
                     "bid_iv": implied_vol(bid, spot, strike, time, rate, q, kind),
                     "ask_iv": implied_vol(ask, spot, strike, time, rate, q, kind),
                     **base, "linear_pnl": linear*factor, "delta_gamma_vega": second*factor,
                     "repriced_pnl": (exact-base["price"])*factor})
    return {"spot": spot, "time_years": time, "contract_size": contract,
            "shock_spot": shock_spot, "shock_vol_decimal": shock_iv, "positions": rows,
            **{key: math.fsum(r[key] for r in rows)
               for key in ("linear_pnl", "delta_gamma_vega", "repriced_pnl")}}


def market_making():
    # All fills priced independently of the chronological mid-price path.
    fills = [
        {"side": 1,  "qty": 100, "fill": 4.99, "arrival_mid": 5.00, "future_mid": 4.96},
        {"side": 1,  "qty": 100, "fill": 4.97, "arrival_mid": 4.98, "future_mid": 4.94},
        {"side": -1, "qty": 70,  "fill": 4.97, "arrival_mid": 4.96, "future_mid": 4.99},
        {"side": -1, "qty": 30,  "fill": 5.01, "arrival_mid": 5.00, "future_mid": 5.02},
    ]
    terminal, cost, cash, shares = 4.95, .001, 0, 0
    for row in fills:
        side, n, p, mid, future = (row[k] for k in ("side", "qty", "fill", "arrival_mid", "future_mid"))
        row["spread_capture"] = side * n * (mid - p)
        row["markout"] = side * n * (future - p)
        row["mid_drift_to_close"] = side * n * (terminal - mid)
        row["fee"] = n * cost
        cash -= side * n * p + row["fee"]
        shares += side * n
    return {"fills": fills, "end_mid": terminal, "end_inventory": shares, "cash": cash,
            "equity_pnl": cash + shares * terminal,
            **{key: math.fsum(r[key] for r in fills)
               for key in ("spread_capture", "markout", "mid_drift_to_close", "fee")}}


def main():
    result = {"data_provenance": "synthetic", "futures": futures_roll(),
              "options": options_stress(), "market_making": market_making()}
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "multi-asset.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print("futures pnl", result["futures"]["pnl_ex_collateral"],
          "options stress", round(result["options"]["repriced_pnl"],2),
          "market making pnl", round(result["market_making"]["equity_pnl"],2))


if __name__ == "__main__":
    main()
