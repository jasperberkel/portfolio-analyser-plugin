import sys
import unittest
from decimal import Decimal
from importlib import import_module
from itertools import permutations
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/portfolio-analyser"
sys.path.insert(0, str(PLUGIN))
builder = import_module("skills.portfolio-import.scripts.build_portfolio_snapshot")


def manifest(name, quantity, **fields):
    position = {
        "name": name, "asset_type": "STOCK", "currency": "EUR", "price": "10",
        "quantity": str(quantity), "market_value": str(10 * quantity), **fields,
    }
    return {
        "as_of": "2026-11-07", "base_currency": "EUR", "cash_value": "0",
        "reported_total_value": position["market_value"], "warnings": [], "positions": [position],
    }


class PortfolioImportTests(unittest.TestCase):
    def test_weighted_cost_and_snapshot_id_in_any_lot_order(self):
        lots = [
            manifest("Example", 1, symbol="EX", average_buy_price="5"),
            manifest("EXAMPLE", 3, symbol="EX", average_buy_price="5"),
            manifest("Example", 2, symbol="EX", average_buy_price="19"),
        ]
        expected_cost = Decimal(58) / 6
        reference = builder.build_payload(lots)
        for order in permutations(lots):
            snapshot = builder.build_payload(list(order))
            holding, = snapshot["positions"]
            self.assertEqual(snapshot["snapshot"]["total_value"], "60")
            self.assertEqual(holding["quantity"], "6")
            self.assertEqual(Decimal(holding["average_buy_price"]), expected_cost)
            self.assertEqual(snapshot["snapshot"]["id"], reference["snapshot"]["id"])
            self.assertEqual(snapshot["positions"], reference["positions"])

    def test_distinct_unidentified_assets_with_same_name_in_either_source_order(self):
        stock = manifest("Example", 1)
        bond = manifest("Example", 2, asset_type="BOND")
        forward = builder.build_payload([stock, bond])
        reverse = builder.build_payload([bond, stock])
        self.assertEqual({p["asset_type"] for p in forward["positions"]}, {"BOND", "STOCK"})
        self.assertEqual(forward["snapshot"]["id"], reverse["snapshot"]["id"])
        self.assertEqual(forward["positions"], reverse["positions"])
