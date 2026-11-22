import concurrent.futures
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TICKERS = ("sh510300", "sh510500", "sh518880", "sh000001")
START_YEAR = 2015
END_YEAR = 2025

def fetch(job):
    ticker, year, mode = job
    start, end = f"{year}-01-01", f"{year + 1}-01-10"
    url = BASE + "?" + urlencode({"param": f"{ticker},day,{start},{end},350,{mode}"})
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as response:
        obj = json.load(response)
    if obj["code"] != 0:
        raise ValueError(obj["msg"])
    node = obj["data"][ticker]
    key = mode + "day" if mode else "day"
    if key in node:
        chosen = key
    else:
        raise ValueError((job, list(node)))
    rows = node[chosen]
    if not 240 <= len(rows) <= 270:
        raise ValueError((job, len(rows), rows[:1], rows[-1:]))
    return {"ticker": ticker, "year": year, "requested": mode or "raw", "key": chosen,
            "url": url, "rows": rows}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="New snapshot pathname")
    target = parser.parse_args().output
    jobs = [(ticker, year, "" if ticker == "sh000001" else "qfq")
            for ticker in TICKERS for year in range(START_YEAR, END_YEAR + 1)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        result = list(pool.map(fetch, jobs))
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")
    print([(r["ticker"], r["year"], r["key"],len(r["rows"])) for r in result])

if __name__ == "__main__":
    main()
