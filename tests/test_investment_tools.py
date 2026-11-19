import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "plugins/portfolio-analyser/scripts")
)
from fundamentals import normalize_company_facts
from portfolio_proposals import evaluate_portfolio_proposal, evaluate_plan_targets
from opportunity_screen import screen_opportunities
from candidate_memory import merge_candidates
from v2_fixtures import context, bundle, SOLAR, BATTERY
import research_contract as c


class FundamentalTests(unittest.TestCase):
    def normalize(
        self, rows, cutoff="2026-11-01T12:00:00Z", unit="USD", metric="Revenues"
    ):
        return normalize_company_facts(
            {"cik": 1, "facts": {"us-gaap": {metric: {"units": {unit: rows}}}}},
            cutoff,
            cutoff,
            "1",
        )

    def row(self, **changes):
        return {
            "start": "2026-01-01",
            "end": "2026-06-30",
            "val": 100,
            "form": "10-Q",
            "filed": "2026-08-01",
            "accn": "0001-26-1",
            **changes,
        }

    def test_future_restatement_and_day_precision(self):
        rows = [self.row(), self.row(val=90, filed="2026-11-02", accn="0001-26-2")]
        for cutoff, expected in [
            ("2026-11-01T12:00:00Z", "100"),
            ("2026-11-02T23:00:00Z", "100"),
            ("2026-11-03T06:00:00Z", "90"),
        ]:
            result = self.normalize(rows, cutoff)
            self.assertEqual(result["facts"][0]["value"], expected)
            self.assertIsNone(result["sources"][0]["published_at"])
            self.assertEqual(result["facts"][0]["period"], "2026-01-01/2026-06-30")

    def test_additive_half_year_only_and_no_derived_eps(self):
        rows = [
            self.row(),
            self.row(
                end="2026-12-31",
                val=220,
                form="10-K",
                filed="2027-02-01",
                accn="0001-27-1",
            ),
        ]
        result = self.normalize(rows, "2027-03-01T12:00:00Z")
        derived = next(f for f in result["facts"] if "derived" in f["basis"])
        self.assertEqual(
            (derived["value"], derived["period"]), ("120", "2026-07-01/2026-12-31")
        )
        result = self.normalize(
            rows, "2027-03-01T12:00:00Z", "USD/shares", "EarningsPerShareDiluted"
        )
        self.assertEqual(len(result["facts"]), 2)
        self.assertFalse(any("derived" in f["basis"] for f in result["facts"]))

    def test_nonfinite_and_issuer_mismatch(self):
        with self.assertRaises(ValueError):
            self.normalize([self.row(val="NaN")])
        with self.assertRaisesRegex(ValueError, "issuer"):
            normalize_company_facts(
                {"cik": 2}, "2026-11-01T12:00:00Z", "2026-11-01T12:00:00Z", "1"
            )

    def test_units_and_missing_data_not_zero(self):
        result = self.normalize([self.row()], unit="EUR")
        self.assertEqual(result["facts"][0]["currency"], "EUR")
        self.assertTrue(result["gaps"])
        self.assertFalse(any(f["metric"] == "diluted_eps" for f in result["facts"]))

    def test_trailing_year_requires_contiguous_comparable_quarters(self):
        periods = [
            ("2025-10-01", "2025-12-31"),
            ("2026-01-01", "2026-03-31"),
            ("2026-04-01", "2026-06-30"),
            ("2026-07-01", "2026-09-30"),
        ]
        rows = [self.row(start=a, end=b, filed="2026-10-01") for a, b in periods]

        def ttm(rows):
            return [
                f
                for f in self.normalize(rows)["facts"]
                if "trailing twelve" in f["basis"]
            ]

        self.assertEqual(ttm(rows)[0]["value"], "400")
        rows[1]["start"] = "2026-01-02"
        self.assertEqual(ttm(rows), [])

    def test_screen_reports_coverage_and_ignores_unavailable_facts(self):
        result = self.normalize([self.row()])
        rule = {
            k: result["facts"][0][k]
            for k in ("metric", "unit", "currency", "period", "basis")
        }
        rule.update(operator="gt", threshold="50")
        data = screen_opportunities(
            [SOLAR, BATTERY],
            [{"instrument_id": SOLAR["instrument_id"], **result}],
            [rule],
            "2026-11-01T12:00:00Z",
        )
        self.assertEqual((data["universe_count"], data["assessed_count"]), (2, 1))
        self.assertEqual(
            [r["status"] for r in data["results"]], ["matched", "unassessed"]
        )
        rule["currency"] = "EUR"
        self.assertEqual(
            screen_opportunities(
                [SOLAR],
                [{"instrument_id": SOLAR["instrument_id"], **result}],
                [rule],
                "2026-11-01T12:00:00Z",
            )["assessed_count"],
            0,
        )


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.ctx = context()
        self.p = {k: self.ctx["dashboard"][k] for k in ("snapshot", "positions")}
        self.rules = {
            "currency": "EUR",
            "targets": {SOLAR["instrument_id"]: ".3", "CASH": ".7"},
            "max_exposure": {SOLAR["instrument_id"]: ".4"},
            "cash_buffer": "20",
            "rationale": "Explicit synthetic plan",
        }
        self.proposal = {
            "snapshot_id": self.p["snapshot"]["id"],
            "plan_version": 1,
            "changes": [],
            "cost_reserve": "5",
            "conditional_sales": False,
        }

    def evaluate(self, proposal=None, **kwargs):
        return evaluate_portfolio_proposal(
            self.p, 1, proposal or self.proposal, self.rules, **kwargs
        )

    def test_untouched_positions_cash_and_unknown_lookthrough(self):
        result = self.evaluate()
        self.assertEqual(result["cash_after"], "95")
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(len(result["weights"]), 3)
        self.assertTrue(result["gaps"])

    def test_unfunded_and_conditional_proceeds(self):
        self.proposal["changes"] = [{"instrument": BATTERY, "value_change": "200"}]
        self.assertEqual(self.evaluate()["status"], "blocked")
        self.proposal["changes"].append({"instrument": SOLAR, "value_change": "150"})
        self.assertEqual(self.evaluate()["status"], "blocked")
        self.proposal["changes"][-1]["value_change"] = "-150"
        self.assertIn("conditional_sales", " ".join(self.evaluate()["violations"]))
        self.proposal["conditional_sales"] = True
        result = self.evaluate()
        self.assertEqual(result["cash_after"], "45")
        self.assertFalse(result["violations"])

    def test_overlap_is_checked_against_limit(self):
        fund = self.p["positions"][0]
        evidence = {
            "items": [
                {
                    "instrument_id": fund["isin"],
                    "exposures": [
                        {
                            "instrument_id": SOLAR["instrument_id"],
                            "weight": ".5",
                            "as_of": "2026-10-01T00:00:00Z",
                        }
                    ],
                }
            ]
        }
        self.assertEqual(self.evaluate(dossiers=evidence)["status"], "blocked")

    def test_targets_identity_and_stale_plan(self):
        self.rules["targets"]["CASH"] = ".8"
        with self.assertRaisesRegex(ValueError, "100%"):
            self.evaluate()
        self.rules["targets"]["CASH"] = ".7"
        self.proposal["plan_version"] = 2
        with self.assertRaisesRegex(ValueError, "stale"):
            self.evaluate()

    def test_final_target_is_checked_even_if_small_first_step_passes(self):
        self.rules["targets"] = {SOLAR["instrument_id"]: ".8", "CASH": ".2"}
        self.assertFalse(self.evaluate()["violations"])
        result = evaluate_plan_targets(self.p, 1, self.rules, {"items": []})
        self.assertEqual(result["status"], "blocked")
        self.assertIn("exposure", " ".join(result["violations"]))


class CandidateMemoryTests(unittest.TestCase):
    def test_absent_candidate_keeps_thesis_and_restores_scoped_history(self):
        ctx = context()
        draft = bundle(ctx)
        reports = c.aggregate(
            {r["task_id"]: r for r in draft["research"]}, draft["run_id"]
        )
        memory = merge_candidates([], reports, ctx["research_cutoff"])
        old = copy.deepcopy(memory)
        memory = merge_candidates(memory, [], "2027-01-01T00:00:00Z")
        self.assertEqual(memory, old)
        ctx["candidate_memory"] = memory
        restored = c.scoped_history(ctx, "valuation.thesis", [BATTERY["instrument_id"]])
        self.assertEqual(
            restored["items"][0]["theses"][0]["thesis_id"],
            old[0]["research"]["valuation.thesis"]["item"]["theses"][0]["thesis_id"],
        )
        self.assertTrue(
            all(
                s.startswith(BATTERY["instrument_id"] + ":memory:")
                for s in restored["items"][0]["source_ids"]
            )
        )
        self.assertIsNone(
            c.scoped_history(ctx, "valuation.thesis", [SOLAR["instrument_id"]])
        )


if __name__ == "__main__":
    unittest.main()
