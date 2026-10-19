"""Run deterministic Python checks only; this does not compile or execute MQL5."""
from pathlib import Path
import compileall
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ok = all(compileall.compile_dir(str(ROOT / directory), quiet=1)
             for directory in ("mac_ai", "config", "tests"))
    if not ok:
        return 1
    for directory in ("tests", "config/tests"):
        path = ROOT / directory
        if not path.is_dir():
            continue
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(path), "-p", "test_*.py", "-v"],
            cwd=ROOT, check=False,
        )
        if result.returncode:
            return result.returncode
    api_tests = ROOT / "mac_ai/tests"
    if api_tests.is_dir():
        result = subprocess.run([sys.executable, "-m", "pytest", str(api_tests), "-q"], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    print("Python/static checks passed. MetaEditor compile and MT5 backtest: NOT RUN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
