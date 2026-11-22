import copy
import json
import tempfile
import unittest
from pathlib import Path

from backtest import (BASE_COST, END, ETF, ROOT, SPLIT, START, check_secondary,
                      load_market, metrics, period_rows, rebalance, simulate)


class BacktestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = ROOT / "data/tencent_snapshot.json"
        cls.dates, cls.bars, cls.quality = load_market(cls.snapshot)
        cls.rows, cls.orders, cls.signals = simulate(cls.dates, cls.bars, "momentum")

    def test_first_signal_is_month_end_and_first_fill_is_next_open(self):
        first = self.signals[0]
        self.assertEqual((first["lookback_anchor"], first["signal_date"], first["trade_date"]),
                         ("2015-10-08", "2015-12-31", START))
        self.assertGreater(first["momentum_510500"], first["momentum_510300"])
        self.assertEqual(first["weight_510500"], 1)
        self.assertEqual(self.orders[0]["adjusted_open"], 6.429)
        first_close = self.bars[ETF[1]][START][1]
        self.assertAlmostEqual(self.rows[0]["nav"], first_close / 6.429 / 1.001)

    def test_execution_day_close_cannot_change_same_day_signal_or_fill(self):
        mutated = copy.deepcopy(self.bars)
        bar = mutated[ETF[1]][START]
        mutated[ETF[1]][START] = (bar[0], bar[1] * 1.5, *bar[2:])
        rows, orders, signals = simulate(self.dates, mutated, "momentum")
        self.assertEqual(signals[0], self.signals[0])
        self.assertEqual(orders[0], self.orders[0])
        self.assertNotEqual(rows[0]["nav"], self.rows[0]["nav"])

    def test_month_signal_uses_immediately_preceding_session(self):
        self.assertEqual(len(self.signals), 120)
        for signal in self.signals:
            index = self.dates.index(signal["trade_date"])
            self.assertEqual(signal["signal_date"], self.dates[index - 1])
            self.assertNotEqual(signal["signal_date"][:7], signal["trade_date"][:7])

    def test_budget_has_cash_for_fees_and_counts_both_legs(self):
        values, cash, changes, fee = rebalance({ETF[0]: 1, ETF[1]: 0, ETF[2]: 0},
                                               0, {ETF[1]: 1}, .001)
        self.assertAlmostEqual(cash, 0)
        self.assertAlmostEqual(changes[ETF[0]], -1)
        self.assertAlmostEqual(fee, .001 * (1 + changes[ETF[1]]))
        self.assertAlmostEqual(sum(values.values()) + cash + fee, 1)

    def test_each_fee_reconciles_and_positions_are_funded(self):
        for row in self.rows:
            weight = row["cash_weight"] + sum(row[f"weight_{s[2:]}"] for s in ETF)
            self.assertAlmostEqual(weight, 1)
            self.assertGreaterEqual(row["cash_weight"], 0)
        self.assertAlmostEqual(sum(r["fee"] for r in self.orders), sum(r["cost"] for r in self.rows))
        for order in self.orders:
            self.assertAlmostEqual(order["fee"], order["notional"] * BASE_COST / 10000)

    def test_holdout_uses_previous_close_and_preserves_portfolio_state(self):
        rows = period_rows(self.rows, "holdout")
        start_index = self.dates.index(SPLIT)
        prior_close_day = self.dates[start_index - 1]
        prior_nav = next(row["nav"] for row in self.rows if row["date"] == prior_close_day)
        self.assertEqual(rows[0]["date"], SPLIT)
        self.assertEqual(rows[-1]["date"], END)
        self.assertEqual(len(rows), 727)
        self.assertAlmostEqual(metrics(rows)["total"], rows[-1]["nav"] / prior_nav - 1)

    def test_in_scope_missing_bar_is_rejected(self):
        dirty = json.loads(self.snapshot.read_bytes())
        batch = next(b for b in dirty if b["ticker"] == ETF[0] and b["year"] == 2024)
        batch["rows"] = [r for r in batch["rows"] if r[0] != "2024-03-15"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps(dirty))
            with self.assertRaisesRegex(ValueError, "Calendar mismatch"):
                load_market(path)

    def test_known_out_of_scope_gaps_and_secondary_sample(self):
        self.assertEqual(self.quality["calendar_gaps_all_snapshot"][ETF[1]]["missing"],
                         ["2015-04-13", "2015-04-14"])
        audit = check_secondary(self.bars, ROOT / "data/eastmoney_510300_20251224_20251231.json")
        self.assertEqual(audit["ohlc_match"], 6)

    def test_higher_assumed_cost_reduces_terminal_wealth(self):
        end_values = [simulate(self.dates, self.bars, "momentum", bps=cost)[0][-1]["nav"]
                      for cost in (0, 10, 25, 50)]
        self.assertTrue(all(a > b for a, b in zip(end_values, end_values[1:])))


if __name__ == "__main__":
    unittest.main()
