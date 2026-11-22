"""Run all independent quant lab verification from a clone or an offline bundle."""
import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def python(*args):
    subprocess.run((sys.executable, *args), cwd=ROOT, check=True)


def outputs_match(actual, expected):
    if isinstance(expected, float):
        return isinstance(actual, float) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12)
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            outputs_match(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            outputs_match(a, b) for a, b in zip(actual, expected))
    return actual == expected


def compare_report(actual, expected):
    if not outputs_match(json.loads(actual.read_text(encoding="utf-8")), json.loads(expected.read_text(encoding="utf-8"))):
        raise ValueError(f"Unexpected result: {actual.name}")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--market-data", action="store_true", help="Run ETF baseline and forward tests with frozen bars")
    ap.add_argument("--cpp", action="store_true", help="Compile and verify the C++17 price-level fixture")
    args = ap.parse_args()
    python("-m", "unittest", "discover", "-s", "tests", "-v")
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    files = ["data-plane.json", "multi-asset.json", "portfolio-controls.json", "model-drift.json", "valuation.json"]
    for name in ("data_plane", "multi_asset", "portfolio_controls", "model_drift", "valuation"):
        python("-m", "lab." + name)
    with tempfile.TemporaryDirectory() as temporary:
        db = str(Path(temporary) / "verify.sqlite")
        for report in ("execution.json", "execution-replay.json"):
            python("-m", "lab.execution", "--db", db, "--out", str(out / report))
            files.append(report)
    if args.market_data:
        python("baseline/run.py")
        python("-m", "lab.research")
        files.extend(("research.json", "input-provenance.json"))
        checked = ROOT / "baseline" / "results" / "summary.json"
        compare_report(checked, ROOT / "evidence" / "summary.json")
    for name in files:
        compare_report(out / name, ROOT / "evidence" / name)
    if args.cpp:
        executable = out / "price-levels"
        subprocess.run(("c++", "-std=c++17", "-O3", "-Wall", "-Wextra", "-Werror",
                        str(ROOT/"benchmarks/price_levels.cpp"), "-o", str(executable)), check=True)
        output = subprocess.check_output((str(executable),), text=True)
        report = json.loads(output)
        if not report["dense"]["checksum"] == report["tree"]["checksum"] == 60526080:
            raise ValueError("C++ benchmark outputs disagree")
        print(output.strip(), flush=True)
    print(f"Verified {len(files)} deterministic experiment outputs")


if __name__ == "__main__":
    main()
