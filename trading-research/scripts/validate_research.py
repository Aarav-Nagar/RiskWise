from __future__ import annotations

import csv
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def check_file(path: str) -> pathlib.Path:
    full = ROOT / path
    if not full.exists():
        raise FileNotFoundError(path)
    print(f"ok: {path}")
    return full


def check_no_known_secret_literals() -> None:
    banned_literals = [
        "5BKB" + "YPFT7VMMVK4T",
        "e9Yaz" + "SehwgkFGvz4kDYof4TD0hh4ONtA",
        "3Vf7Wq2q" + "AHhpGDFNgnWecRcHt6rm57MczUDn1YPd",
    ]
    patterns = [
        re.compile(re.escape(value))
        for value in banned_literals
    ]
    for path in ROOT.rglob("*"):
        skipped_parts = {".git", "node_modules", ".venv", "data", "artifacts"}
        if path.is_dir() or any(part in skipped_parts for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in patterns:
            if pattern.search(text):
                raise RuntimeError(f"Secret-like literal found in {path}")
    print("ok: no known API key literals found")


def check_big_game_summary() -> None:
    path = check_file("arena/results/big_game_2025-05-01_2026-05-01_summary.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_agent = {row["agent"]: row for row in rows}
    committee = float(by_agent["Options_CommitteeVeto"]["ending_value"])
    raw = float(by_agent["OptionsOnly_NoIntervention"]["ending_value"])
    if committee <= 2000:
        raise AssertionError("Committee veto agent did not finish above 2x in saved summary.")
    if raw >= 1000:
        raise AssertionError("No-intervention options agent did not show the expected blow-up in saved summary.")
    print("ok: big game summary matches expected headline behavior")


def main() -> int:
    run([sys.executable, "-m", "compileall", "ai_trading_arena", "tests"])
    run([sys.executable, "-m", "pytest"])
    check_file("README.md")
    check_file("docs/AUDIT_CHECKLIST.md")
    check_file("docs/REPRODUCING_RESULTS.md")
    check_file("reports/big_game_research_report.md")
    check_file("arena/figures/big_game_2025-05-01_2026-05-01_equity.png")
    check_file("arena/figures/big_game_2025-05-01_2026-05-01_monthly_ranks.png")
    check_big_game_summary()
    check_no_known_secret_literals()
    print("validation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
