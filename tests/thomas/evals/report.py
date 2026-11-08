"""Grade recorded Thomas eval sessions without making model calls."""

import argparse
import hashlib
import json
from pathlib import Path

from grade import grade

CASES = Path(__file__).with_name("cases.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assess(case, directory, reviews):
    path = directory / (case["id"] + ".json")
    row = {"case": case["id"], "trace": path.name,
           "case_sha256": digest(json.dumps(case, sort_keys=True).encode())}
    if not path.is_file():
        return {**row, "status": "incomplete", "reason": "missing trace"}
    raw = path.read_bytes()
    row["trace_sha256"] = digest(raw)
    try:
        trace = json.loads(raw)
        if trace["id"] != case["id"] or trace["prompt"] != case["prompt"]:
            return {**row, "status": "incomplete", "reason": "trace belongs to another case or prompt"}
        for key in ("model", "harness", "transport", "plugin_version", "wheel_sha256", "image_id"):
            if key in trace:
                row[key] = trace[key]
        if trace["status"] == "transport_smoke":
            return {**row, "status": "transport_only"}
        if trace["status"] != "ok" or trace.get("complete") is not True:
            return {**row, "status": "incomplete", "reason": trace.get("error") or trace["status"]}
        checks = grade(case, trace)
    except (KeyError, TypeError, ValueError) as exc:
        return {**row, "status": "incomplete", "reason": f"invalid trace: {exc}"}
    row.update(checks=checks, manual_review=case["manual_review"])
    if not checks or not all(value is True for value in checks.values()):
        return {**row, "status": "failed"}
    review = reviews.get(case["id"], {})
    if (review.get("trace_sha256") == row["trace_sha256"]
            and review.get("case_sha256") == row["case_sha256"]
            and review.get("verdict") in ("pass", "fail") and str(review.get("note") or "").strip()):
        return {**row, "status": "passed" if review["verdict"] == "pass" else "failed", "review": review}
    return {**row, "status": "review"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("traces", type=Path, help="directory of <case-id>.json traces from live.py")
    parser.add_argument("--case", action="append", help="only report this case (repeatable)")
    parser.add_argument("--reviews", type=Path, help="qualitative verdicts on the recorded answers, keyed by case ID")
    parser.add_argument("--json", type=Path, help="write the machine-readable report here")
    args = parser.parse_args()
    cases = json.loads(CASES.read_text())
    ids = {case["id"] for case in cases}
    if args.case and set(args.case) - ids:
        parser.error(f"unknown case; choose from {sorted(ids)}")
    try:
        reviews = json.loads(args.reviews.read_text()) if args.reviews else {}
        if not isinstance(reviews, dict) or not all(isinstance(v, dict) for v in reviews.values()):
            raise ValueError("reviews must be an object keyed by case ID")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    rows = []
    for case in cases:
        if args.case and case["id"] not in args.case:
            continue
        row = assess(case, args.traces, reviews)
        rows.append(row)
        failed = [name for name, ok in row.get("checks", {}).items() if not ok]
        print(f"{row['case']}: {row['status']}", row.get("reason") or ", ".join(failed))
        if row["status"] == "review":
            print("  Review:", row["manual_review"])
    if args.json:
        args.json.write_text(json.dumps({"cases": rows}, indent=2, ensure_ascii=False) + "\n")
    if any(row["status"] == "failed" for row in rows):
        return 1
    if any(row["status"] != "passed" for row in rows):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
