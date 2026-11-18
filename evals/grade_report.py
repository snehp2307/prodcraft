#!/usr/bin/env python3
"""Grade a prodcraft report against the planted-issue ground truth.

A finding counts as caught when the report mentions its file (if one is given)
and at least one of its keywords within the same finding block. Also checks the
required report sections and the verdict.

Usage:
    python3 evals/grade_report.py PRODCRAFT_REPORT.md [--expected evals/expected_findings.json]
    python3 evals/grade_report.py PRODCRAFT_REPORT.md --min-recall 0.8   # CI gate
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_EXPECTED = Path(__file__).with_name("expected_findings.json")


def split_blocks(report: str) -> list[str]:
    """Split the report into finding blocks on '### ' headings; fall back to the whole text."""
    blocks = re.split(r"\n(?=### )", report)
    return blocks if len(blocks) > 1 else [report]


def is_caught(finding: dict, blocks: list[str]) -> bool:
    file_ref = finding.get("file")
    keywords = [k.lower() for k in finding["keywords"]]
    for block in blocks:
        text = block.lower()
        if file_ref and file_ref.lower() not in text:
            continue
        if any(k in text for k in keywords):
            return True
    return False


def grade(report: str, expected: dict) -> dict:
    blocks = split_blocks(report)
    caught = [f["id"] for f in expected["findings"] if is_caught(f, blocks)]
    missed = [f["id"] for f in expected["findings"] if f["id"] not in caught]
    sections_missing = [s for s in expected["required_sections"] if s.lower() not in report.lower()]
    verdict_ok = expected["expected_verdict"].lower() in report.lower()
    total = len(expected["findings"])
    return {
        "recall": round(len(caught) / total, 3) if total else 1.0,
        "caught": caught,
        "missed": missed,
        "sections_missing": sections_missing,
        "verdict_ok": verdict_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected", type=Path, default=DEFAULT_EXPECTED)
    parser.add_argument("--min-recall", type=float, default=None,
                        help="exit non-zero if recall is below this value")
    args = parser.parse_args(argv)

    result = grade(args.report.read_text(encoding="utf-8"),
                   json.loads(args.expected.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))

    passed = not result["sections_missing"] and result["verdict_ok"]
    if args.min_recall is not None:
        passed = passed and result["recall"] >= args.min_recall
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
