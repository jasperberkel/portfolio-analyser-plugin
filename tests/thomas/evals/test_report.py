import json
import tempfile
import unittest
from pathlib import Path

from report import CASES, assess, digest


class ReportTests(unittest.TestCase):
    def test_pass_requires_matching_human_review_and_completed_model_turn(self):
        case = next(c for c in json.loads(CASES.read_text()) if c["id"] == "missing_attachment")
        trace = {"id": case["id"], "prompt": case["prompt"], "tool_calls": [], "status": "ok",
                 "complete": True, "assistant_text": "Bitte lade den Depotauszug hoch."}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / (case["id"] + ".json")
            path.write_text(json.dumps(trace))
            row = assess(case, directory, {})
            self.assertEqual(row["status"], "review")
            reviews = {case["id"]: {"trace_sha256": row["trace_sha256"],
                       "case_sha256": digest(json.dumps(case, sort_keys=True).encode()),
                       "verdict": "pass", "note": "Fragt nach dem fehlenden Beleg."}}
            self.assertEqual(assess(case, directory, reviews)["status"], "passed")
            path.write_text(json.dumps({**trace, "assistant_text": "Ich habe 500 Euro importiert."}))
            self.assertEqual(assess(case, directory, reviews)["status"], "review")
            path.write_text(json.dumps({**trace, "status": "transport_smoke"}))
            self.assertEqual(assess(case, directory, reviews)["status"], "transport_only")
