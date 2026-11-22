import math
import unittest

from lab.jd_catalog import FAMILIES, ROOT, load_register, render
from lab.model_drift import score
from lab.multi_asset import european, futures_roll, implied_vol, market_making, options_stress
from lab.portfolio_controls import reconcile, search_portfolios


class MarketLabTests(unittest.TestCase):
    def test_futures_roll_does_not_earn_the_contract_price_gap(self):
        r = futures_roll()
        self.assertEqual(r["sum_variation"], 160)
        self.assertEqual(r["naive_stitched_variation"] - r["sum_variation"], 120)
        self.assertAlmostEqual(r["ending_cash"] - r["initial_deposit"] - r["extra_collateral"], 148)

    def test_implied_vol_and_put_call_parity(self):
        s, k, t, rate, q, vol = 5., 5.2, .25, .02, .01, .23
        c = european(s, k, t, rate, q, vol, "call")["price"]
        p = european(s, k, t, rate, q, vol, "put")["price"]
        self.assertAlmostEqual(c-p, s*math.exp(-q*t)-k*math.exp(-rate*t))
        self.assertAlmostEqual(implied_vol(c, s, k, t, rate, q, "call"), vol)

    def test_option_full_repricing_is_not_linear_in_the_stress_fixture(self):
        r = options_stress()
        self.assertTrue(all(p["bid_iv"] < p["ask_iv"] for p in r["positions"]))
        self.assertAlmostEqual(r["repriced_pnl"], 4976.573411199299)
        self.assertGreater(abs(r["repriced_pnl"]-r["linear_pnl"]), 200)

    def test_market_maker_pnl_is_cash_plus_inventory_and_components(self):
        r = market_making()
        self.assertAlmostEqual(r["equity_pnl"], r["spread_capture"]+r["mid_drift_to_close"]-r["fee"])
        self.assertGreater(r["spread_capture"], 0)
        self.assertLess(r["equity_pnl"], 0)

    def test_constraints_change_the_portfolio_chosen_on_identical_forecasts(self):
        r = search_portfolios()
        self.assertEqual((r["candidates"], r["feasible"]), (375, 58))
        self.assertGreater(r["budget_and_position_cap_only"]["two_sided_turnover"], .30)
        selected = r["fully_constrained"]
        self.assertEqual(selected["weights_percent"], [40, 10, 25, 25])
        self.assertLessEqual(selected["annual_tracking_error"], .04)

    def test_reconciliation_classifies_missing_and_mismatched_ids(self):
        row1 = ("A", "x", "buy", 10, 100)
        row2 = ("B", "x", "sell", 10, 104)
        row3 = ("C", "y", "sell", 30, 102)
        result = reconcile([row1, row1, row2], [(*row1[:-1], 101), row3])
        self.assertEqual(result["local_duplicates"], ["A"])
        self.assertEqual(result["field_mismatches"], ["A"])
        self.assertEqual(result["missing_locally"], ["C"])
        self.assertEqual(result["missing_externally"], ["B"])

    def test_upstream_features_shift_and_the_frozen_model_loses_to_zero(self):
        r = score()
        stable, shift = r["stable_validation"], r["shifted_forward"]
        self.assertLess(r["train_range"][1], stable["range"][0])
        self.assertLess(stable["rmse"], stable["zero_forecast_rmse"])
        self.assertGreater(shift["rmse"], shift["zero_forecast_rmse"])
        self.assertFalse(stable["feature_shift_alert"])
        self.assertTrue(shift["feature_shift_alert"])

    def test_catalog_has_evidence_for_every_family_and_is_reproducible(self):
        source, records = load_register(ROOT / "catalog/jd-register.txt")
        self.assertEqual({f for _, kind, _, f, _ in records if kind != "线索"}, set(FAMILIES))
        self.assertEqual(render(source, records), (ROOT / "catalog/jd-catalog.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
