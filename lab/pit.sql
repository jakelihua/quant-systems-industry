CREATE TABLE features (
    symbol TEXT NOT NULL,
    economic_date TEXT NOT NULL,
    available_at TEXT NOT NULL,
    revision INTEGER NOT NULL,
    value INTEGER NOT NULL,
    PRIMARY KEY (symbol, economic_date, available_at, revision)
);
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    cutoff TEXT NOT NULL
);
INSERT INTO features VALUES
    ('ETF-X','2025-03-31','2025-04-10T09:00:00Z',1,100),
    ('ETF-X','2025-03-31','2025-04-15T09:00:00Z',2,80),
    ('ETF-X','2025-06-30','2025-07-10T09:00:00Z',1,120);
INSERT INTO decisions VALUES
    ('a','ETF-X','2025-04-09T09:00:00Z'),
    ('b','ETF-X','2025-04-11T09:00:00Z'),
    ('c','ETF-X','2025-04-16T09:00:00Z');

CREATE VIEW naive_latest AS
SELECT id, cutoff, (
    SELECT value FROM features f
    WHERE f.symbol = d.symbol AND f.economic_date <= substr(d.cutoff, 1, 10)
    ORDER BY economic_date DESC, revision DESC LIMIT 1
) AS feature
FROM decisions d ORDER BY id;

CREATE VIEW known_at_decision AS
SELECT id, cutoff, (
    SELECT value FROM features f
    WHERE f.symbol = d.symbol AND f.economic_date <= substr(d.cutoff, 1, 10)
      AND f.available_at <= d.cutoff
    ORDER BY economic_date DESC, available_at DESC, revision DESC LIMIT 1
) AS feature
FROM decisions d ORDER BY id;
