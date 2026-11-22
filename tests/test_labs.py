import copy
import tempfile
import unittest
from pathlib import Path

from baseline import backtest as bt
from lab.data_plane import Book, pit_example
from lab.execution import Journal, run_demo
from lab.research import select_windows

ROOT = Path(__file__).resolve().parents[1]


class DataTests(unittest.TestCase):
    def test_late_revision_does_not_leak(self):
        result = pit_example()
        self.assertEqual([r[2] for r in result["naive_latest"]], [80, 80, 80])
        self.assertEqual([r[2] for r in result["as_known"]], [None, 100, 80])

    def test_gap_invalidates_and_snapshot_recovers(self):
        book = Book()
        book.snapshot(10, [(499, 800)], [(501, 200)])
        self.assertAlmostEqual(book.top()["microprice"], 500.6)
        self.assertEqual(book.delta(11, "ask", 501, 100), "APPLIED")
        self.assertEqual(book.delta(11, "ask", 501, 100), "DUPLICATE")
        self.assertEqual(book.delta(13, "bid", 499, 400), "SEQUENCE_GAP_OR_CONFLICT")
        self.assertIsNone(book.top())
        self.assertEqual(book.delta(14, "ask", 501, 300), "WAITING_FOR_SNAPSHOT")
        book.snapshot(15, [(500, 300)], [(502, 600)])
        self.assertEqual(book.top()["mid"], 501)

    def test_same_seq_with_different_payload_closes_feed(self):
        book = Book()
        book.snapshot(10, [(499, 800)], [(501, 200)])
        book.delta(11, "ask", 501, 100)
        self.assertEqual(book.delta(11, "ask", 501, 150), "SEQUENCE_GAP_OR_CONFLICT")
        self.assertIsNone(book.top())


class ExecutionTests(unittest.TestCase):
    def test_replay_is_idempotent_and_reconciles_tca(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "desk.sqlite"
            first = run_demo(path, ROOT / "lab/fixture.json")
            resumed = run_demo(path, ROOT / "lab/fixture.json")
        self.assertEqual(first["unique_persisted_events"], 11)
        self.assertEqual(resumed["new_events_this_run"], 0)
        self.assertEqual(first["desk"], resumed["desk"])
        self.assertEqual(first["desk"]["orders"]["A"]["status"], "CANCELED")
        self.assertEqual(first["desk"]["cash_fen"], 169890)
        self.assertEqual(first["desk"]["positions"]["ETF-X"], 60)
        self.assertEqual(first["desk"]["rejected"], {
            "STALE": "STALE_OR_MISSING_QUOTE", "HALTED": "KILL_SWITCH"})
        self.assertEqual(first["tca"]["A"]["implementation_shortfall_bps"], 70)

    def test_failed_write_keeps_journal_replayable(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "desk.sqlite")
            try:
                quote = {"kind": "quote", "at_ms": 1000,
                         "data": {"symbol": "ETF-X", "bid": 499, "ask": 501, "exchange_ms": 998}}
                self.assertTrue(journal.append("quote:1", quote))
                with self.assertRaisesRegex(ValueError, "source key conflicts"):
                    journal.append("quote:1", {**quote, "at_ms": 1001})
                with self.assertRaisesRegex(ValueError, "Unknown order"):
                    journal.append("bad-fill", {"kind": "fill", "at_ms": 1002, "data": {"id": "missing"}})
                self.assertEqual(journal.replay().last_timestamp, 1000)
                self.assertEqual(journal.db.execute("SELECT count(*) FROM events").fetchone()[0], 1)
            finally:
                journal.close()


@unittest.skipUnless((ROOT / "baseline/data/tencent_snapshot.json").exists(),
                     "Frozen data distributed with the personal offline package")
class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates, cls.bars, _ = bt.load_market(ROOT / "baseline/data/tencent_snapshot.json")
        cls.runs = {window: bt.simulate(cls.dates, cls.bars, "momentum", window)[0]
                    for window in bt.WINDOWS}

    def test_selection_does_not_use_held_out_returns(self):
        altered = copy.deepcopy(self.runs)
        for row in altered[120]:
            if row["date"][:4] >= "2025":
                row["daily_return"] = 0.90
        before, evidence = select_windows(self.runs)
        after, _ = select_windows(altered)
        self.assertEqual(before, after)
        for row in evidence:
            self.assertLess(int(row["last_training_date"][:4]), row["forward_year"])

    def test_schedule_keeps_pre_2019_strategy_timestamps(self):
        _, _, signals = bt.simulate(self.dates, self.bars, "momentum", annual_lookbacks={2019:20})
        dates = self.dates
        for signal in signals:
            year = signal["trade_date"][:4]
            self.assertEqual(dates.index(signal["signal_date"]) - dates.index(signal["lookback_anchor"]),
                             20 if year == "2019" else 60)


if __name__ == "__main__":
    unittest.main()
