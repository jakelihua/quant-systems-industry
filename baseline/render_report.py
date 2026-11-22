import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    results = ROOT / "results"
    payload = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    payload["quality"] = json.loads((results / "quality.json").read_text(encoding="utf-8"))
    series = defaultdict(list)
    with (results / "daily.csv").open(encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            series[row["method"]].append([row["date"], round(float(row["nav"]), 8)])
    payload["series"] = series
    with (results / "signals.csv").open(encoding="utf-8-sig") as stream:
        payload["signals"] = list(csv.DictReader(stream))
    template = (ROOT / "report_template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", r"\u003c")
    output = ROOT / "研究看板.html"
    output.write_text(template.replace("__REPORT_DATA__", data), encoding="utf-8")
    print(output.name)

if __name__ == "__main__":
    main()
