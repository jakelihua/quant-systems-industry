"""Synthetic market data recovery and point-in-time join exercises."""
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Book:
    sequence: int = 0
    valid: bool = False
    levels: dict = field(default_factory=lambda: {"bid": {}, "ask": {}})
    last_message: tuple = ()

    def check_levels(self, levels):
        bids, asks = levels["bid"], levels["ask"]
        if any(type(p) is not int or type(q) is not int or min(p, q) <= 0
               for side in (bids, asks) for p, q in side.items()):
            raise ValueError("A depth level must have positive integer price and quantity")
        if bids and asks and max(bids) >= min(asks):
            raise ValueError("Crossed or locked book in the continuous-session fixture")

    def snapshot(self, seq, bids, asks):
        if seq <= self.sequence:
            raise ValueError("Recovery snapshot must move forward")
        candidate = {"bid": dict(bids), "ask": dict(asks)}
        self.check_levels(candidate)
        self.levels, self.valid, self.sequence = candidate, True, seq
        self.last_message = ()

    def delta(self, seq, side, price, size):
        message = (seq, side, price, size)
        if not self.valid:
            return "WAITING_FOR_SNAPSHOT"
        if seq == self.sequence and message == self.last_message:
            return "DUPLICATE"
        if seq != self.sequence + 1:
            self.valid = False
            return "SEQUENCE_GAP_OR_CONFLICT"
        if side not in self.levels or type(price) is not int or type(size) is not int or price <= 0 or size < 0:
            raise ValueError("Invalid price-level update")
        candidate = {key: values.copy() for key, values in self.levels.items()}
        if size:
            candidate[side][price] = size
        else:
            candidate[side].pop(price, None)
        try:
            self.check_levels(candidate)
        except ValueError:
            self.valid = False
            raise
        self.levels, self.sequence, self.last_message = candidate, seq, message
        return "APPLIED"

    def top(self):
        bids, asks = self.levels["bid"], self.levels["ask"]
        if not self.valid or not bids or not asks:
            return None
        bid, ask = max(bids), min(asks)
        bq, aq = bids[bid], asks[ask]
        return {"bid": bid, "ask": ask, "bid_size": bq, "ask_size": aq,
                "mid": (bid + ask) / 2, "spread_ticks": ask - bid,
                "queue_imbalance": (bq - aq) / (bq + aq),
                "microprice": (ask * bq + bid * aq) / (bq + aq)}


def pit_example():
    # available_at is the recorded usable time of this revision, after vendor and ingest delay.
    with sqlite3.connect(":memory:") as db:
        db.executescript((Path(__file__).parent / "pit.sql").read_text(encoding="utf-8"))
        naive = [list(row) for row in db.execute("SELECT * FROM naive_latest")]
        pit = [list(row) for row in db.execute("SELECT * FROM known_at_decision")]
    return {"columns": ["decision_id", "cutoff", "feature"], "naive_latest": naive, "as_known": pit}


def main():
    book = Book()
    book.snapshot(10, [(499, 800)], [(501, 200)])
    before = book.top()
    next_update = (11, "ask", 501, 100)
    steps = [book.delta(*next_update), book.delta(*next_update),
             book.delta(13, "bid", 499, 400), book.delta(14, "ask", 501, 300)]
    during_gap = book.top()
    book.snapshot(15, [(500, 300)], [(502, 600)])
    result = {"provenance": "synthetic", "initial_top": before, "delta_status": steps,
              "top_during_gap": during_gap, "recovered_top": book.top(), "point_in_time": pit_example()}
    out = Path(__file__).resolve().parents[1] / "out"
    out.mkdir(exist_ok=True)
    (out / "data-plane.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(f"Quote after gap: {during_gap}; as-known decisions: {result['point_in_time']['as_known']}")


if __name__ == "__main__":
    main()
