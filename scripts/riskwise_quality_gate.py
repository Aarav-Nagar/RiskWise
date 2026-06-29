from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend" / "mobile-demo"
REPORT_DIR = ROOT / "docs" / "qa_runs"


@dataclass
class GateStep:
    step_id: str
    label: str
    command: str
    cwd: Path
    required: bool = True
    parse_eval_summary: bool = False


def build_steps(args: argparse.Namespace) -> list[GateStep]:
    steps: list[GateStep] = []
    if not args.skip_backend:
      steps.append(GateStep("backend_tests", "Backend contract tests", "python -m pytest api/tests -q", BACKEND))
    if not args.skip_ai:
        limit = f" --limit {args.eval_limit}" if args.eval_limit and args.eval_limit > 0 else ""
        steps.append(
            GateStep(
                "ai_quality_eval",
                "RiskWiseAI curated evals",
                f"python api/evals/ai_quality_eval.py{limit} --progress-every {args.eval_progress_every}",
                BACKEND,
                parse_eval_summary=True,
            )
        )
        if args.stress_count and args.stress_count > 0:
            steps.append(
                GateStep(
                    "ai_stress_eval",
                    f"RiskWiseAI generated stress eval ({args.stress_count})",
                    f"python api/evals/ai_stress_eval.py --count {args.stress_count} --progress-every {args.stress_progress_every}",
                    BACKEND,
                    parse_eval_summary=True,
                )
            )
    if not args.skip_frontend:
        steps.append(GateStep("frontend_typecheck", "Mobile demo typecheck", "npm run typecheck", FRONTEND))
        steps.append(GateStep("frontend_export", "Mobile demo web export", "npm run export:web", FRONTEND))
        if args.ui:
            steps.append(GateStep("frontend_smoke", "Mobile demo Playwright smoke", "npm run qa:smoke", FRONTEND))
    return steps


def run_step(step: GateStep) -> dict[str, Any]:
    started = time.perf_counter()
    print(f"\n[RiskWise gate] Starting {step.step_id}: {step.command}", flush=True)
    process = subprocess.Popen(
        step.command,
        cwd=step.cwd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output_parts: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        output_parts.append(line)
        print(line, end="", flush=True)
    returncode = process.wait()
    duration = round(time.perf_counter() - started, 2)
    output = "".join(output_parts)
    summary = parse_json_summary(output) if step.parse_eval_summary else None
    passed = returncode == 0
    if summary and "failed" in summary:
        passed = passed and int(summary.get("failed") or 0) == 0
    print(f"[RiskWise gate] Finished {step.step_id}: {'PASS' if passed else 'FAIL'} in {duration}s", flush=True)
    return {
        "id": step.step_id,
        "label": step.label,
        "command": step.command,
        "cwd": str(step.cwd),
        "required": step.required,
        "passed": passed,
        "returncode": returncode,
        "duration_seconds": duration,
        "summary": summary,
        "output_tail": output[-5000:],
    }


def parse_json_summary(output: str) -> dict[str, Any] | None:
    clean = output.strip()
    if not clean:
        return None
    start = clean.rfind("{")
    if start < 0:
        return None
    try:
        return json.loads(clean[start:])
    except json.JSONDecodeError:
        return None


def write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"quality_gate_{stamp}.json"
    md_path = REPORT_DIR / f"quality_gate_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# RiskWise Quality Gate",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Status: `{'PASS' if payload['passed'] else 'FAIL'}`",
        f"Steps: `{payload['passed_steps']}/{payload['total_steps']}` passed",
        "",
        "## Steps",
        "",
    ]
    for step in payload["steps"]:
        mark = "PASS" if step["passed"] else "FAIL"
        lines.extend(
            [
                f"### {mark} - {step['label']}",
                "",
                f"Command: `{step['command']}`",
                f"Duration: `{step['duration_seconds']}s`",
                f"Return code: `{step['returncode']}`",
                "",
            ]
        )
        if step.get("summary"):
            lines.append("Summary:")
            lines.append("")
            lines.append(f"```json\n{json.dumps(step['summary'], indent=2)}\n```")
            lines.append("")
        if not step["passed"] and step.get("output_tail"):
            lines.append("Output tail:")
            lines.append("")
            lines.append(f"```text\n{step['output_tail']}\n```")
            lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RiskWise production quality gate.")
    parser.add_argument("--skip-backend", action="store_true", help="Skip backend pytest.")
    parser.add_argument("--skip-ai", action="store_true", help="Skip RiskWiseAI evals.")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend typecheck/export.")
    parser.add_argument("--ui", action="store_true", help="Also run Playwright mobile-demo smoke tests.")
    parser.add_argument("--eval-limit", type=int, default=0, help="Limit curated AI eval cases. 0 runs all cases.")
    parser.add_argument("--eval-progress-every", type=int, default=5, help="Print curated AI eval progress every N cases.")
    parser.add_argument("--stress-count", type=int, default=0, help="Run generated AI stress evals with this many cases.")
    parser.add_argument("--stress-progress-every", type=int, default=25, help="Print stress-eval progress every N cases.")
    parser.add_argument("--no-report", action="store_true", help="Do not write docs/qa_runs reports.")
    args = parser.parse_args()

    steps = build_steps(args)
    if not steps:
        print(json.dumps({"passed": False, "error": "No quality gate steps selected."}, indent=2))
        raise SystemExit(2)

    results = [run_step(step) for step in steps]
    required_failures = [result for result in results if result["required"] and not result["passed"]]
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not required_failures,
        "passed_steps": sum(1 for result in results if result["passed"]),
        "total_steps": len(results),
        "steps": results,
    }
    if not args.no_report:
        json_path, md_path = write_report(payload)
        payload["report_json"] = str(json_path)
        payload["report_markdown"] = str(md_path)

    print(
        json.dumps(
            {
                "passed": payload["passed"],
                "passed_steps": payload["passed_steps"],
                "total_steps": payload["total_steps"],
                "report_json": payload.get("report_json"),
                "report_markdown": payload.get("report_markdown"),
                "failed_steps": [result["id"] for result in required_failures],
            },
            indent=2,
        )
    )
    if required_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
