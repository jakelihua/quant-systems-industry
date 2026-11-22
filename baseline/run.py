import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    for arguments in (("-m", "unittest", "-v"), ("backtest.py",), ("render_report.py",)):
        subprocess.run((sys.executable, *arguments), cwd=ROOT, check=True)
