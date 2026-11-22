"""Synthetic rates/FX and fund accounting examples with explicit units."""
import json
from pathlib import Path


def bond_price(face, annual_coupon, yield_rate, years):
    return sum(face * annual_coupon / (1 + yield_rate)**t for t in range(1, years+1)) + face / (1+yield_rate)**years


def rates_and_fx():
    # Annual coupons, just after a coupon date. No accrued interest in the base price.
    face, coupon, y, years = 100, .03, .04, 5
    bond = lambda rate: bond_price(face, coupon, rate, years)
    start = bond(y)
    dv01 = (bond(y-.0001)-bond(y+.0001))/2
    shock_pnl = bond(y+.005)-start
    # USD per EUR under simple annual interest; both rates share the same horizon.
    spot, usd, eur, term = 1.08, .04, .025, .5
    forward = spot * (1+usd*term)/(1+eur*term)
    eur_notional = 100_000
    market_at_delivery = 1.10
    pnl = eur_notional * (market_at_delivery-forward)
    return {"bond_price_per_100": start, "dv01_positive_loss_per_100_face": dv01,
            "rate_shock_bps": 50, "linear_rate_shock_pnl": -50*dv01, "repriced_rate_shock_pnl": shock_pnl,
            "fx_quote_convention": "USD per EUR", "simple_interest_forward": forward,
            "forward_eur_notional": eur_notional, "delivery_spot": market_at_delivery,
            "long_eur_forward_pnl_usd_at_delivery": pnl}


def fund_nav():
    # External subscription occurs at the just-struck closing NAV, with no issue costs.
    assets, liabilities, shares = 1_005_000, 5_000, 1_000_000
    prior_unit_nav = (assets-liabilities)/shares
    investment_pnl = -20_000
    closing_assets = assets + investment_pnl
    closing_unit_nav = (closing_assets-liabilities)/shares
    subscription = 98_000
    issued = subscription / closing_unit_nav
    post_flow_nav = (closing_assets + subscription - liabilities)/(shares + issued)
    return {"prior_unit_nav": prior_unit_nav, "close_unit_nav": closing_unit_nav,
            "post_subscription_unit_nav": post_flow_nav, "issued_units": issued,
            "investment_return": closing_unit_nav/prior_unit_nav-1,
            "prior_net_assets": assets-liabilities,
            "closing_net_assets_after_flow": closing_assets+subscription-liabilities}


def main():
    result = {"data_provenance": "synthetic", "rates_and_fx": rates_and_fx(), "fund_nav": fund_nav()}
    out = Path(__file__).resolve().parents[1] / "out"
    out.mkdir(exist_ok=True)
    (out / "valuation.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
