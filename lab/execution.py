"""SQLite event replay for a synthetic execution desk. Prices and cash are integer fen."""
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

BUY, SELL = 1, -1
MAX_QUOTE_AGE_MS = 150
MAX_ORDER_FEN = 100_000


@dataclass
class Order:
    symbol: str
    side: int
    quantity: int
    limit: int
    arrival_mid_x2: int
    filled: int = 0
    status: str = "PENDING_ACK"
    gross_fen: int = 0
    fee_fen: int = 0


@dataclass
class Desk:
    cash_fen: int = 200_000
    positions: dict = field(default_factory=dict)
    quotes: dict = field(default_factory=dict)
    orders: dict = field(default_factory=dict)
    rejected: dict = field(default_factory=dict)
    kill_switch: bool = False
    last_timestamp: int = -1

    def apply(self, event):
        kind, now, fields = event["kind"], event["at_ms"], event["data"]
        if type(now) is not int or now < self.last_timestamp:
            raise ValueError("Event arrival times must be nondecreasing integers")
        if kind == "quote":
            self.record_quote(fields, now)
        elif kind == "halt":
            self.kill_switch = True
        elif kind == "submit":
            self.submit(fields, now)
        elif kind in ("ack", "fill", "cancel_request", "cancel_ack", "reject"):
            self.order_update(kind, fields)
        else:
            raise ValueError(f"Unknown event type: {kind}")
        self.last_timestamp = now

    def record_quote(self, data, now):
        symbol, bid, ask, exchange_ms = (data[k] for k in ("symbol", "bid", "ask", "exchange_ms"))
        if not 0 < bid <= ask or not 0 <= exchange_ms <= now:
            raise ValueError("Invalid market quote")
        previous = self.quotes.get(symbol)
        if previous and exchange_ms < previous[2]:
            raise ValueError("Exchange quote is out of order")
        self.quotes[symbol] = (bid, ask, exchange_ms)

    def submit(self, data, now):
        key, symbol, side, size, price = (data[k] for k in ("id", "symbol", "side", "quantity", "limit"))
        if key in self.orders or key in self.rejected:
            raise ValueError(f"Order ID is already in use: {key}")
        if side not in (BUY, SELL) or type(size) is not int or type(price) is not int or min(size, price) <= 0:
            raise ValueError("Invalid order parameters")
        quote = self.quotes.get(symbol)
        working = [o for o in self.orders.values()
                   if o.status in ("PENDING_ACK", "WORKING", "PARTIAL", "PENDING_CANCEL")]
        # Fee reserve is one fen per unfilled share. Each simulated fill enforces the same bound.
        reserved_cash = sum((o.quantity - o.filled) * (o.limit + 1) for o in working if o.side == BUY)
        reserved_shares = sum(o.quantity - o.filled for o in working
                              if o.side == SELL and o.symbol == symbol)
        if self.kill_switch:
            reason = "KILL_SWITCH"
        elif not quote or now - quote[2] > MAX_QUOTE_AGE_MS:
            reason = "STALE_OR_MISSING_QUOTE"
        elif size * price > MAX_ORDER_FEN:
            reason = "MAX_ORDER_NOTIONAL"
        elif side == BUY and size * (price + 1) > self.cash_fen - reserved_cash:
            reason = "INSUFFICIENT_UNRESERVED_CASH"
        elif side == SELL and size > self.positions.get(symbol, 0) - reserved_shares:
            reason = "INSUFFICIENT_UNRESERVED_POSITION"
        else:
            self.orders[key] = Order(symbol, side, size, price, quote[0] + quote[1])
            return
        self.rejected[key] = reason

    def order_update(self, kind, data):
        order = self.orders.get(data["id"])
        if not order:
            raise ValueError("Unknown order for venue event")
        state = order.status
        if kind == "ack" and state == "PENDING_ACK":
            order.status = "WORKING"
        elif kind == "reject" and state == "PENDING_ACK":
            order.status = "REJECTED"
        elif kind == "cancel_request" and state in ("WORKING", "PARTIAL"):
            order.status = "PENDING_CANCEL"
        elif kind == "cancel_ack" and state == "PENDING_CANCEL":
            order.status = "CANCELED"
        elif kind == "fill" and state in ("WORKING", "PARTIAL", "PENDING_CANCEL"):
            self.fill(order, data)
        else:
            raise ValueError(f"Invalid transition {state} + {kind}")

    def fill(self, order, data):
        size, price, fee = (data[k] for k in ("quantity", "price", "fee"))
        if any(type(v) is not int for v in (size, price, fee)):
            raise ValueError("Fill fields must be integer")
        if not 0 < size <= order.quantity - order.filled or price <= 0 or not 0 <= fee <= size:
            raise ValueError("Invalid fill quantity, price, or fee")
        if order.side * (price - order.limit) > 0:
            raise ValueError("Fill violates the order limit")
        gross = price * size
        shares = self.positions.get(order.symbol, 0) + order.side * size
        cash = self.cash_fen - order.side * gross - fee
        if min(shares, cash) < 0:
            raise ValueError("Fill would violate position or cash accounting")
        self.positions[order.symbol], self.cash_fen = shares, cash
        order.filled += size
        order.gross_fen += gross
        order.fee_fen += fee
        if order.filled == order.quantity:
            order.status = "FILLED"
        elif order.status != "PENDING_CANCEL":
            order.status = "PARTIAL"


class Journal:
    def __init__(self, database):
        self.db = sqlite3.connect(database, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL)""")

    def close(self):
        self.db.close()

    def replay(self):
        state = Desk()
        for (body,) in self.db.execute("SELECT body FROM events ORDER BY seq"):
            state.apply(json.loads(body))
        return state

    def append(self, source_key, event):
        body = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute("SELECT body FROM events WHERE source_key=?", (source_key,)).fetchone()
            if existing:
                if existing[0] != body:
                    raise ValueError(f"Event source key conflicts: {source_key}")
                self.db.execute("COMMIT")
                return False
            self.replay().apply(event)
            self.db.execute("INSERT INTO events(source_key,body) VALUES (?,?)", (source_key, body))
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise


def tca(order, end_mid_fen):
    arrival = order.arrival_mid_x2 / 2
    filled_cost = order.side * (order.gross_fen - arrival * order.filled)
    opportunity = order.side * (end_mid_fen - arrival) * (order.quantity - order.filled)
    return {"arrival_mid_fen": arrival, "end_mid_fen": end_mid_fen,
            "filled_price_cost_fen": filled_cost, "fee_fen": order.fee_fen,
            "unfilled_opportunity_fen": opportunity,
            "implementation_shortfall_fen": filled_cost + order.fee_fen + opportunity,
            "implementation_shortfall_bps": (filled_cost + order.fee_fen + opportunity) /
                                            (arrival * order.quantity) * 10_000}


def run_demo(path, fixture):
    journal = Journal(path)
    try:
        events = json.loads(Path(fixture).read_text(encoding="utf-8"))
        accepted = sum(journal.append(row["source_key"], row["event"]) for row in events)
        state = journal.replay()
        result = {"data_provenance": "synthetic; prices are not historical quotes",
                  "unique_persisted_events": journal.db.execute("SELECT count(*) FROM events").fetchone()[0],
                  "new_events_this_run": accepted, "desk": asdict(state),
                  "tca": {key: tca(order, sum(state.quotes[order.symbol][:2])/2)
                          for key, order in state.orders.items()}}
        return result
    finally:
        journal.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--db", type=Path, default=root / "out/desk.sqlite")
    parser.add_argument("--out", type=Path, default=root / "out/execution.json")
    args = parser.parse_args()
    for directory in {args.db.parent, args.out.parent}:
        directory.mkdir(parents=True, exist_ok=True)
    report = run_demo(args.db, root / "lab/fixture.json")
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['unique_persisted_events']} unique events, {report['new_events_this_run']} appended")
