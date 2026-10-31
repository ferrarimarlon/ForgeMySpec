#!/usr/bin/env python3
"""Invoice generator CLI.

Reads an invoice JSON file, validates it (reporting every error at once),
computes totals using Decimal arithmetic, and prints a text invoice or
exports JSON.

Input format:
{
  "invoice_number": "INV-001",          (optional)
  "date": "2026-10-31",                 (optional, YYYY-MM-DD)
  "currency": "$",                      (optional symbol/code prefix, default "$")
  "customer": {"name": "Acme", "email": "a@b.co", "address": "..."},
  "items": [{"description": "Widget", "quantity": 3, "unit_price": 9.99}],
  "tax_rate": 8.5,                      (percent, 0-100, default 0)
  "discount": {"type": "percent", "value": 10}   (optional; "percent" or "fixed")
}

Calculation: each line total = round(quantity * unit_price); subtotal = sum of
line totals; discount is taken off the subtotal; tax is charged on the
discounted amount; all rounded half-up to cents.
"""

import argparse
import json
import sys
from datetime import date as _date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
HUNDRED = Decimal(100)


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def money(x):
    """Round to cents, half-up (the conventional commercial rounding)."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(x):
    return f"{money(x):,.2f}"


def is_number(v):
    return isinstance(v, (int, Decimal)) and not isinstance(v, bool) and (
        not isinstance(v, Decimal) or v.is_finite()
    )


def validate(data):
    """Return (errors, parsed). parsed is only meaningful if errors is empty."""
    errors = []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"], None

    def num_field(value, path, *, minimum=None, maximum=None, positive=False):
        if not is_number(value):
            errors.append(f"{path}: must be a number")
            return None
        d = Decimal(value)
        if positive and d <= 0:
            errors.append(f"{path}: must be greater than 0")
        elif minimum is not None and d < minimum:
            errors.append(f"{path}: must be at least {minimum}")
        elif maximum is not None and d > maximum:
            errors.append(f"{path}: must be at most {maximum}")
        return d

    def opt_str(obj, key, path):
        v = obj.get(key)
        if v is not None and not isinstance(v, str):
            errors.append(f"{path}.{key}: must be a string")

    # Header fields
    for key in ("invoice_number", "currency"):
        if key in data and not isinstance(data[key], str):
            errors.append(f"{key}: must be a string")
    if "date" in data:
        d = data["date"]
        try:
            if not isinstance(d, str):
                raise ValueError
            _date.fromisoformat(d)
        except ValueError:
            errors.append("date: must be a valid date in YYYY-MM-DD format")

    # Customer
    customer = data.get("customer")
    if customer is None:
        errors.append("customer: required")
    elif not isinstance(customer, dict):
        errors.append("customer: must be an object")
    else:
        name = customer.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append("customer.name: required, must be a non-empty string")
        opt_str(customer, "email", "customer")
        opt_str(customer, "address", "customer")
        email = customer.get("email")
        if isinstance(email, str) and email and "@" not in email:
            errors.append("customer.email: must contain '@'")

    # Items
    items = data.get("items")
    parsed_items = []
    if items is None:
        errors.append("items: required")
    elif not isinstance(items, list):
        errors.append("items: must be an array")
    elif not items:
        errors.append("items: must contain at least one item")
    else:
        for i, item in enumerate(items):
            p = f"items[{i}]"
            if not isinstance(item, dict):
                errors.append(f"{p}: must be an object")
                continue
            desc = item.get("description")
            if not isinstance(desc, str) or not desc.strip():
                errors.append(f"{p}.description: required, must be a non-empty string")
            for key in ("quantity", "unit_price"):
                if key not in item:
                    errors.append(f"{p}.{key}: required")
            qty = (num_field(item["quantity"], f"{p}.quantity", positive=True)
                   if "quantity" in item else None)
            price = (num_field(item["unit_price"], f"{p}.unit_price", minimum=Decimal(0))
                     if "unit_price" in item else None)
            if isinstance(desc, str) and qty is not None and price is not None:
                parsed_items.append((desc, qty, price))

    # Tax rate
    tax_rate = Decimal(0)
    if "tax_rate" in data:
        t = num_field(data["tax_rate"], "tax_rate", minimum=Decimal(0), maximum=HUNDRED)
        if t is not None:
            tax_rate = t

    # Discount
    discount = None
    if data.get("discount") is not None:
        disc = data["discount"]
        if not isinstance(disc, dict):
            errors.append("discount: must be an object")
        else:
            dtype = disc.get("type")
            if dtype not in ("percent", "fixed"):
                errors.append("discount.type: must be \"percent\" or \"fixed\"")
            if "value" not in disc:
                errors.append("discount.value: required")
            else:
                maximum = HUNDRED if dtype == "percent" else None
                v = num_field(disc["value"], "discount.value",
                              minimum=Decimal(0), maximum=maximum)
                if dtype in ("percent", "fixed") and v is not None:
                    discount = (dtype, v)

    if errors:
        return errors, None
    return [], {
        "invoice_number": data.get("invoice_number"),
        "date": data.get("date"),
        "currency": data.get("currency", "$"),
        "customer": customer,
        "items": parsed_items,
        "tax_rate": tax_rate,
        "discount": discount,
    }


def compute(inv):
    lines = []
    for desc, qty, price in inv["items"]:
        lines.append({"description": desc, "quantity": qty, "unit_price": price,
                      "line_total": money(qty * price)})
    subtotal = sum((l["line_total"] for l in lines), Decimal(0))

    discount_amount = Decimal(0)
    if inv["discount"]:
        dtype, value = inv["discount"]
        if dtype == "percent":
            discount_amount = money(subtotal * value / HUNDRED)
        else:
            discount_amount = money(value)
    if discount_amount > subtotal:
        raise ValidationError(
            [f"discount: amount {fmt(discount_amount)} exceeds subtotal {fmt(subtotal)}"])

    taxable = subtotal - discount_amount
    tax = money(taxable * inv["tax_rate"] / HUNDRED)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "discount": discount_amount,
        "taxable": taxable,
        "tax": tax,
        "total": taxable + tax,
    }


def qty_str(q):
    s = format(q.normalize() if isinstance(q, Decimal) else Decimal(q), "f")
    return s


def render_text(inv, res):
    cur = inv["currency"]
    out = []
    out.append("INVOICE" + (f" {inv['invoice_number']}" if inv["invoice_number"] else ""))
    if inv["date"]:
        out.append(f"Date: {inv['date']}")
    c = inv["customer"]
    out.append("")
    out.append("Bill to:")
    out.append(f"  {c['name']}")
    for key in ("email", "address"):
        if c.get(key):
            out.append(f"  {c[key]}")
    out.append("")

    rows = [(l["description"], qty_str(l["quantity"]),
             cur + fmt(l["unit_price"]), cur + fmt(l["line_total"]))
            for l in res["lines"]]
    heads = ("Description", "Qty", "Unit Price", "Total")
    w = [max(len(heads[i]), *(len(r[i]) for r in rows)) for i in range(4)]
    line = lambda r: (f"{r[0]:<{w[0]}}  {r[1]:>{w[1]}}  {r[2]:>{w[2]}}  {r[3]:>{w[3]}}")
    out.append(line(heads))
    out.append("-" * len(line(heads)))
    out.extend(line(r) for r in rows)
    out.append("-" * len(line(heads)))

    summary = [("Subtotal", res["subtotal"])]
    if inv["discount"]:
        dtype, value = inv["discount"]
        label = f"Discount ({qty_str(value)}%)" if dtype == "percent" else "Discount"
        summary.append((label, -res["discount"]))
    summary.append((f"Tax ({qty_str(inv['tax_rate'])}%)", res["tax"]))
    summary.append(("TOTAL", res["total"]))
    vals = [(k, ("-" if v < 0 else "") + cur + fmt(abs(v))) for k, v in summary]
    total_w = len(line(heads))
    vw = max(len(v) for _, v in vals)
    for k, v in vals:
        out.append(f"{k:<{total_w - vw - 2}}  {v:>{vw}}")
    return "\n".join(out)


def to_json(inv, res):
    d = lambda x: format(money(x), "f")
    discount = None
    if inv["discount"]:
        discount = {"type": inv["discount"][0], "value": qty_str(inv["discount"][1])}
    return {
        "invoice_number": inv["invoice_number"],
        "date": inv["date"],
        "currency": inv["currency"],
        "customer": inv["customer"],
        "items": [{"description": l["description"], "quantity": qty_str(l["quantity"]),
                   "unit_price": qty_str(l["unit_price"]), "line_total": d(l["line_total"])}
                  for l in res["lines"]],
        "tax_rate": qty_str(inv["tax_rate"]),
        "discount_input": discount,
        "subtotal": d(res["subtotal"]),
        "discount": d(res["discount"]),
        "taxable_amount": d(res["taxable"]),
        "tax": d(res["tax"]),
        "total": d(res["total"]),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an invoice from a JSON file.")
    ap.add_argument("input", help="invoice JSON file ('-' for stdin)")
    ap.add_argument("-f", "--format", choices=("text", "json"), default="text",
                    help="output format (default: text)")
    ap.add_argument("-o", "--output", help="write output to file instead of stdout")
    args = ap.parse_args(argv)

    try:
        if args.input == "-":
            raw = sys.stdin.read()
        else:
            with open(args.input, encoding="utf-8") as fh:
                raw = fh.read()
    except OSError as e:
        print(f"error: cannot read {args.input}: {e.strerror or e}", file=sys.stderr)
        return 2
    try:
        data = json.loads(raw, parse_float=Decimal, parse_constant=lambda c: Decimal("NaN"))
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON: {e}", file=sys.stderr)
        return 2

    errors, inv = validate(data)
    if not errors:
        try:
            res = compute(inv)
        except ValidationError as e:
            errors = e.errors
    if errors:
        print(f"Invalid invoice: {len(errors)} error(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    text = (render_text(inv, res) if args.format == "text"
            else json.dumps(to_json(inv, res), indent=2))
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError as e:
            print(f"error: cannot write {args.output}: {e.strerror or e}", file=sys.stderr)
            return 2
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
