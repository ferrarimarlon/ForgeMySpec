import ast
import contextlib
import io
import json
import os
import tempfile
import unittest
from decimal import Decimal

import invoice_gen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def good():
    return {
        "customer": {"name": "Acme"},
        "items": [{"description": "Widget", "quantity": 2, "unit_price": 9.99}],
        "tax_rate": 10,
    }


def load(text):
    return json.loads(text, parse_float=Decimal)


def run_cli(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = invoice_gen.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class ValidationTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(invoice_gen.validate(load(json.dumps(good()))), [])

    def test_reports_all_errors(self):
        inv = {
            "customer": {"name": ""},
            "items": [
                {"description": "A", "quantity": 0, "unit_price": 1},
                {"description": "", "quantity": 1, "unit_price": -5},
                {"description": "C", "quantity": "x", "unit_price": 1},
            ],
            "tax_rate": 150,
            "discount": {"type": "percent", "value": 120},
        }
        errs = invoice_gen.validate(inv)
        joined = "\n".join(errs)
        for path in ("customer.name", "items[0].quantity", "items[1].description",
                     "items[1].unit_price", "items[2].quantity", "tax_rate", "discount.value"):
            self.assertIn(path, joined)
        self.assertEqual(len(errs), 7)

    def test_bool_and_missing(self):
        errs = invoice_gen.validate({"items": [{"description": "x", "quantity": True,
                                                "unit_price": 1}], "tax_rate": None})
        joined = "\n".join(errs)
        for path in ("customer", "items[0].quantity", "tax_rate"):
            self.assertIn(path, joined)

    def test_fixed_discount_over_subtotal(self):
        inv = good()
        inv["discount"] = {"type": "fixed", "value": 100}
        self.assertTrue(any("discount.value" in e for e in invoice_gen.validate(inv)))


class ComputeTests(unittest.TestCase):
    def test_half_up_rounding_and_grand_total(self):
        inv = load('{"customer":{"name":"A"},"items":[{"description":"x","quantity":3,'
                   '"unit_price":0.125}],"tax_rate":5}')
        c = invoice_gen.compute(inv)
        self.assertEqual(c["lines"][0]["line_total"], Decimal("0.38"))
        inv = load('{"customer":{"name":"A"},"items":[{"description":"x","quantity":1,'
                   '"unit_price":10.05}],"tax_rate":5}')
        c = invoice_gen.compute(inv)
        self.assertEqual(c["tax"], Decimal("0.50"))
        self.assertEqual(c["total"], Decimal("10.55"))

    def test_discount_percent_and_fixed(self):
        inv = load('{"customer":{"name":"A"},"items":[{"description":"x","quantity":3,'
                   '"unit_price":33.33}],"tax_rate":8.25,"discount":{"type":"percent","value":15}}')
        c = invoice_gen.compute(inv)
        self.assertEqual(c["subtotal"], Decimal("99.99"))
        self.assertEqual(c["discount"], Decimal("15.00"))  # 14.9985 -> 15.00
        self.assertEqual(c["tax"], Decimal("7.01"))        # 84.99*.0825=7.011675
        self.assertEqual(c["total"], c["subtotal"] - c["discount"] + c["tax"])
        inv["discount"] = {"type": "fixed", "value": 10}
        c = invoice_gen.compute(inv)
        self.assertEqual(c["discount"], Decimal("10.00"))
        self.assertEqual(c["total"], Decimal("89.99") + Decimal("7.42"))  # 7.424175

    def test_no_float_drift(self):
        inv = load('{"customer":{"name":"A"},"items":[{"description":"x","quantity":3,'
                   '"unit_price":0.10}],"tax_rate":0}')
        self.assertEqual(invoice_gen.compute(inv)["total"], Decimal("0.30"))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, text):
        p = os.path.join(self.dir.name, "inv.json")
        with open(p, "w") as f:
            f.write(text)
        return p

    def test_text_and_json_output(self):
        inv = good()
        inv.update(number="INV-1", discount={"type": "percent", "value": 10})
        p = self.write(json.dumps(inv))
        code, out, _ = run_cli([p])
        self.assertEqual(code, 0)
        for s in ("INVOICE #INV-1", "Acme", "Widget", "Subtotal", "Discount", "Tax (10%)", "TOTAL", "19.78"):
            self.assertIn(s, out)
        code, out, _ = run_cli([p, "--format", "json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["subtotal"], "19.98")
        self.assertEqual(data["discount"], "2.00")
        self.assertEqual(data["tax"], "1.80")
        self.assertEqual(data["total"], "19.78")
        self.assertEqual(data["items"][0]["line_total"], "19.98")

    def test_exit_codes(self):
        self.assertEqual(run_cli([os.path.join(self.dir.name, "nope.json")])[0], 2)
        self.assertEqual(run_cli([self.write("not json")])[0], 2)
        code, _, err = run_cli([self.write('{"items": [], "tax_rate": -1}')])
        self.assertEqual(code, 1)
        for s in ("customer", "items", "tax_rate"):
            self.assertIn(s, err)
        self.assertEqual(run_cli([self.write(json.dumps(good()))])[0], 0)


class StructureTests(unittest.TestCase):
    def test_only_stdlib_imports(self):
        path = os.path.join(ROOT, "invoice_gen.py")
        with open(path) as f:
            tree = ast.parse(f.read())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                names.add(n.module.split(".")[0])
        self.assertTrue(names)
        self.assertTrue(names <= {"argparse", "json", "sys", "decimal"}, names)


if __name__ == "__main__":
    unittest.main()
