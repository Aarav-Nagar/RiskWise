"""Challenge concept-coverage threshold sweep.

Loads the hand-labelable fixture at fixtures/challenge_grading_fixture.json
(~40 Challenge answers spanning correct / wrong-but-fluent /
right-topic-wrong-claim / off-topic), scores each answer's concept coverage
against its dimension's anchors, sweeps the coverage threshold, and prints a
precision/recall table for the "answer covers the dimension's concepts"
decision.

IMPORTANT: the fixture labels were drafted by the model and are NOT ground
truth until a human reviews them ("human_reviewed" per row). The sweep is
still useful for choosing a starting threshold, but re-run it after label
review before trusting the shipped value.

Coverage ground truth per label:
  covered      = correct, right_topic_wrong_claim
  not covered  = wrong_but_fluent, off_topic
(right-topic-wrong-claim answers ARE topically covered — catching the wrong
claim is the local LLM rubric's job, not the embedding layer's.)

Run:  python api/evals/challenge_grading_eval.py
It uses the local Ollama embedding model when reachable and records which
basis (local_embedding_nomic vs keyword_overlap_fallback) produced the table;
thresholds for the two bases are separate constants in
services/challenge/grading.py and each must be swept on its own basis.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.services.challenge.anchors import CONCEPT_ANCHORS
from api.services.challenge.embeddings import cosine, embed_texts, keyword_coverage
from api.services.challenge.grading import COVERAGE_THRESHOLD_EMBEDDING, COVERAGE_THRESHOLD_KEYWORD

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "challenge_grading_fixture.json"
COVERED_LABELS = {"correct", "right_topic_wrong_claim"}
SWEEP_START = 0.05
SWEEP_END = 0.90
SWEEP_STEP = 0.05


def load_fixture() -> dict[str, Any]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    rows = payload.get("answers") or []
    unreviewed = sum(1 for row in rows if not row.get("human_reviewed"))
    if unreviewed:
        print(
            f"WARNING: {unreviewed}/{len(rows)} fixture labels are model-drafted and not human-reviewed yet. "
            "Treat this sweep as provisional until the labels are checked.",
            flush=True,
        )
    return payload


async def coverage_scores(rows: list[dict[str, Any]]) -> tuple[list[float], str]:
    """Score every fixture answer; returns (scores, basis)."""
    answers = [str(row.get("answer") or "") for row in rows]
    anchor_lists = [CONCEPT_ANCHORS.get(str(row.get("dimension") or ""), []) for row in rows]
    flat: list[str] = list(answers)
    offsets: list[tuple[int, int]] = []
    for anchors in anchor_lists:
        start = len(flat)
        flat.extend(anchors)
        offsets.append((start, len(flat)))
    vectors = await embed_texts(flat)
    if vectors is not None:
        scores = []
        for index in range(len(rows)):
            start, end = offsets[index]
            scores.append(max((cosine(vectors[index], vectors[position]) for position in range(start, end)), default=0.0))
        return scores, "local_embedding_nomic"
    return [keyword_coverage(answers[index], anchor_lists[index]) for index in range(len(rows))], "keyword_overlap_fallback"


def sweep(rows: list[dict[str, Any]], scores: list[float]) -> list[dict[str, Any]]:
    truths = [str(row.get("label") or "") in COVERED_LABELS for row in rows]
    table = []
    threshold = SWEEP_START
    while threshold <= SWEEP_END + 1e-9:
        predictions = [score >= threshold for score in scores]
        tp = sum(1 for p, t in zip(predictions, truths) if p and t)
        fp = sum(1 for p, t in zip(predictions, truths) if p and not t)
        fn = sum(1 for p, t in zip(predictions, truths) if not p and t)
        tn = sum(1 for p, t in zip(predictions, truths) if not p and not t)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        table.append(
            {
                "threshold": round(threshold, 2),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
            }
        )
        threshold += SWEEP_STEP
    return table


def per_label_breakdown(rows: list[dict[str, Any]], scores: list[float], threshold: float) -> dict[str, dict[str, int]]:
    breakdown: dict[str, dict[str, int]] = {}
    for row, score in zip(rows, scores):
        label = str(row.get("label") or "")
        bucket = breakdown.setdefault(label, {"covered": 0, "not_covered": 0})
        bucket["covered" if score >= threshold else "not_covered"] += 1
    return breakdown


def write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = results_dir / f"challenge_grading_eval_{stamp}.json"
    md_path = results_dir / f"challenge_grading_eval_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Challenge Concept-Coverage Threshold Sweep",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Coverage basis: `{payload['basis']}`",
        f"Fixture rows: `{payload['total']}` (human-reviewed: `{payload['human_reviewed_rows']}`)",
        "",
        "> Labels are model-drafted until a human reviews the fixture; re-run this sweep after review.",
        "",
        "| threshold | precision | recall | F1 | TP | FP | FN | TN |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["sweep"]:
        lines.append(
            f"| {row['threshold']:.2f} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} "
            f"| {row['tp']} | {row['fp']} | {row['fn']} | {row['tn']} |"
        )
    lines.extend(
        [
            "",
            f"Best F1 threshold on this basis: `{payload['best_threshold']}` (F1 `{payload['best_f1']}`)",
            f"Currently shipped threshold for this basis: `{payload['shipped_threshold']}`",
            "",
            "Per-label predictions at the best threshold:",
            "",
            "```json",
            json.dumps(payload["per_label_at_best"], indent=2),
            "```",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


async def run() -> dict[str, Any]:
    fixture = load_fixture()
    rows = fixture.get("answers") or []
    scores, basis = await coverage_scores(rows)
    table = sweep(rows, scores)
    best = max(table, key=lambda row: (row["f1"], row["threshold"]))
    shipped = COVERAGE_THRESHOLD_EMBEDDING if basis == "local_embedding_nomic" else COVERAGE_THRESHOLD_KEYWORD
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "basis": basis,
        "total": len(rows),
        "human_reviewed_rows": sum(1 for row in rows if row.get("human_reviewed")),
        "sweep": table,
        "best_threshold": best["threshold"],
        "best_f1": best["f1"],
        "shipped_threshold": shipped,
        "per_label_at_best": per_label_breakdown(rows, scores, best["threshold"]),
        "scores": [
            {"id": row.get("id"), "dimension": row.get("dimension"), "label": row.get("label"), "coverage": round(score, 4)}
            for row, score in zip(rows, scores)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep the Challenge concept-coverage threshold over the labeled fixture.")
    parser.parse_args()
    payload = asyncio.run(run())
    json_path, md_path = write_report(payload)
    print(
        json.dumps(
            {
                "basis": payload["basis"],
                "best_threshold": payload["best_threshold"],
                "best_f1": payload["best_f1"],
                "shipped_threshold": payload["shipped_threshold"],
                "json": str(json_path),
                "markdown": str(md_path),
            },
            indent=2,
        )
    )
    print()
    print("| threshold | precision | recall | F1 |")
    print("|---|---|---|---|")
    for row in payload["sweep"]:
        print(f"| {row['threshold']:.2f} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} |")


if __name__ == "__main__":
    main()
