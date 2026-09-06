import copy
import json
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins/portfolio-analyser"
sys.path.insert(0, str(ROOT / "scripts"))
import research_contract as c
import workflow as w
from v2_fixtures import BATTERY, ETF, SOLAR, bundle, context, result


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.ctx = context()
        w.initialize(self.path, self.ctx, c.default_workflow())

    def finish(self, task_id, **kwargs):
        task = w.start(self.path, task_id)
        row = result(task, **kwargs)
        w.write(self.path / task_id / "result.json", row)
        state = w.collect(self.path, task_id)
        self.assertEqual(state["tasks"][task_id]["status"], "complete", state)
        return row

    def test_dependencies_and_parallel_readiness(self):
        self.assertEqual(
            set(w.read_state(self.path)["ready_tasks"]), {"market", "holdings"}
        )
        with self.assertRaises(ValueError):
            w.start(self.path, "valuation")
        self.finish("holdings")
        self.assertEqual(
            set(w.read_state(self.path)["ready_tasks"]), {"market", "risk"}
        )
        self.finish("risk")  # Does not wait for candidate valuation.
        self.finish("market")
        self.finish("candidates")
        self.finish("valuation")
        draft = w.draft(self.path)
        reports = c.aggregate(
            {r["task_id"]: r for r in draft["research"]}, draft["run_id"]
        )
        self.assertEqual(len(reports), 4)
        instruments = next(
            r for r in reports if r["analysis_type"] == "instrument.research"
        )["research_data"]
        self.assertEqual(len(instruments["items"]), 3)
        c.validate_payload(
            instruments,
            "instruments",
            [ETF["instrument_id"], SOLAR["instrument_id"], BATTERY["instrument_id"]],
            self.ctx["research_cutoff"],
        )

    def test_duplicate_candidates_reuse_held_dossiers(self):
        self.finish("market", candidates=[SOLAR])
        state = w.read_state(self.path)
        self.assertEqual(state["tasks"]["candidates"]["status"], "complete")
        self.assertEqual(state["tasks"]["candidates"]["attempts"], 0)
        self.finish("holdings")
        task = w.start(self.path, "valuation")
        self.assertEqual(len(task["selected"]), 2)
        self.assertEqual(task["hypotheses"], ["Speichertechnik könnte wachsen."])

    def test_zero_candidates_and_cash_only(self):
        other = self.path / "cash"
        ctx = context()
        ctx["dashboard"]["positions"] = []
        ctx["dashboard"]["snapshot"]["cash_value"] = "1000"
        state = w.initialize(other, ctx, c.default_workflow())
        self.assertEqual(state["tasks"]["holdings"]["status"], "complete")
        market = w.start(other, "market")
        w.write(other / "market/result.json", result(market, candidates=[]))
        state = w.collect(other, "market")
        self.assertEqual(state["tasks"]["candidates"]["status"], "complete")
        self.assertEqual(state["tasks"]["valuation"]["status"], "complete")
        risk = w.start(other, "risk")
        self.assertEqual(risk["calculations"]["cash"], "1000")
        self.assertEqual(risk["selected"], [])

    def test_privacy_inputs(self):
        market = w.start(self.path, "market")
        for text in (
            "Solar",
            "Welt-ETF",
            "PRIVATE",
            "market_value",
            "current_portfolio",
        ):
            self.assertNotIn(text, json.dumps(market))
        held = w.start(self.path, "holdings")
        for text in ("PRIVATE", "market_value", "cash_value", "quantity"):
            self.assertNotIn(text, json.dumps(held))

    def test_retry_limit_and_invalidation(self):
        self.finish("market")
        self.finish("holdings")
        self.finish("candidates")
        self.finish("valuation")
        self.finish("risk")
        state = w.workflow_v2.invalidate(self.path, ["holdings"])
        self.assertEqual(state["tasks"]["market"]["status"], "complete")
        self.assertEqual(state["tasks"]["candidates"]["status"], "complete")
        self.assertEqual(state["tasks"]["valuation"]["status"], "blocked")
        self.assertEqual(state["tasks"]["risk"]["status"], "blocked")
        w.start(self.path, "holdings")
        w.collect(self.path, "holdings", failed=True)
        w.start(self.path, "holdings")
        state = w.collect(self.path, "holdings", failed=True)
        self.assertTrue(state["stopped"])
        with self.assertRaises(ValueError):
            w.draft(self.path)

    def test_stale_descendant_rejected(self):
        for task in ("market", "holdings", "candidates", "valuation", "risk"):
            self.finish(task)
        held = w.read(self.path / "holdings/accepted.json")
        held["content_markdown"] += " corrected"
        w.write(self.path / "holdings/accepted.json", held)
        with self.assertRaisesRegex(ValueError, "provenance"):
            w.draft(self.path)

    def test_exact_coverage_and_source_references(self):
        task = w.start(self.path, "holdings")
        row = result(task)
        row["coverage"]["researched"] = []
        with self.assertRaisesRegex(ValueError, "coverage"):
            c.validate_result(row, task)
        row = result(task)
        row["research_data"]["items"][0]["facts"][0]["source_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "source reference"):
            c.validate_result(row, task)

    def test_risk_example_and_unknown(self):
        self.finish("holdings")
        risk = w.start(self.path, "risk")["calculations"]
        solar = next(
            e for e in risk["exposures"] if e["instrument_id"] == SOLAR["instrument_id"]
        )
        self.assertEqual(Decimal(solar["total"]), Decimal(360))
        self.assertEqual(Decimal(solar["portfolio_weight"]), Decimal(".36"))
        dossier = w.read(self.path / "holdings/accepted.json")["research_data"]
        next(i for i in dossier["items"] if i["instrument"]["asset_type"] == "ETF")[
            "exposures"
        ] = []
        calc = c.portfolio_risk(self.ctx["dashboard"], dossier)
        self.assertTrue(calc["unknown"])
        self.assertEqual(
            next(
                e["indirect"]
                for e in calc["exposures"]
                if e["instrument_id"] == SOLAR["instrument_id"]
            ),
            "0",
        )

    def test_noncomparable_values_and_margin_points(self):
        fact = dict(
            metric="margin",
            unit="percent",
            currency=None,
            period="2026-Q2",
            basis="GAAP",
            value_kind="actual",
            value="22",
        )
        baseline = {**fact, "value_kind": "guidance", "value": "20"}
        self.assertEqual(c.compare_facts(fact, baseline)["difference"], "2")
        for key, value in [
            ("unit", "EUR"),
            ("period", "2026-Q1"),
            ("basis", "adjusted"),
            ("currency", "USD"),
        ]:
            with self.assertRaises(ValueError):
                c.compare_facts(fact, {**baseline, key: value})

    def test_thesis_dates_and_history_scope(self):
        raw = bundle(self.ctx)
        reports = c.aggregate({r["task_id"]: r for r in raw["research"]}, raw["run_id"])
        self.ctx["previous_reports"] = {r["analysis_type"]: r for r in reports}
        history = c.scoped_history(
            self.ctx, "valuation.thesis", [SOLAR["instrument_id"]]
        )
        self.assertEqual(
            [i["instrument_id"] for i in history["items"]], [SOLAR["instrument_id"]]
        )
        changed = copy.deepcopy(history)
        changed["items"][0]["theses"][0]["changed_at"] = "2026-10-01T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "redated"):
            c.validate_continuity(changed, history)

    def test_strategy_followup_and_frozen_publication(self):
        for task_id in ("market", "holdings", "candidates", "valuation", "risk"):
            self.finish(task_id)
        prepared = {
            "source_fingerprint": self.ctx["source_fingerprint"],
            "evidence_fingerprint": "e" * 64,
            "dashboard": {
                "plan": self.ctx["dashboard"]["plan"],
                "reports": [{"analysis_type": t} for t in c.TYPES],
            },
        }
        task = w.prepared(self.path, prepared)
        self.assertEqual(task["contract_version"], 2)
        request = {
            "contract_version": 2,
            "run_id": task["run_id"],
            "evidence_fingerprint": "e" * 64,
            "status": "needs_research",
            "requests": [{"task_id": "market", "questions": ["Portfolio?"]}],
        }
        with self.assertRaises(ValueError):
            w.accept_strategy(self.path, request)
        request["requests"] = [
            {"task_id": "holdings", "questions": ["Marge nachprüfen."]}
        ]
        w.accept_strategy(self.path, request)
        for task_id in ("holdings", "valuation", "risk"):
            self.finish(task_id)
        task = w.prepared(self.path, prepared)
        with self.assertRaises(ValueError):
            w.accept_strategy(self.path, request)
        w.accept_strategy(
            self.path,
            {
                "contract_version": 2,
                "run_id": task["run_id"],
                "evidence_fingerprint": "e" * 64,
                "status": "complete",
                "expected_plan_version": 1,
                "strategy": {
                    "title": "Strategie",
                    "content_markdown": "Keine neue Allokation.",
                },
            },
        )
        packet = w.publication(self.path)
        self.assertEqual(packet["workflow"]["contract_version"], 2)
        self.assertEqual(packet, w.publication(self.path))
        self.assertEqual(len(packet["research"]), 5)

    def test_duplicate_holding_instruments_are_researched_once(self):
        ctx = context()
        ctx["dashboard"]["positions"].append(dict(ctx["dashboard"]["positions"][0]))
        state = w.initialize(self.path / "duplicates", ctx, c.default_workflow())
        task = w.start(self.path / "duplicates", "holdings")
        self.assertEqual(len(task["selected"]), 2)

    def test_ready_queue_removes_started_and_includes_retry(self):
        w.start(self.path, "market")
        self.assertNotIn("market", w.read_state(self.path)["ready_tasks"])
        w.collect(self.path, "market", failed=True)
        self.assertIn("market", w.read_state(self.path)["ready_tasks"])

    def test_v2_requires_v2_app(self):
        ctx = context()
        ctx["contract_version"] = 1
        with self.assertRaisesRegex(ValueError, "Upgrade"):
            w.initialize(self.path / "bad", ctx, c.default_workflow())


if __name__ == "__main__":
    unittest.main()
