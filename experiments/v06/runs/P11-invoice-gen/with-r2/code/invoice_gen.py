#!/usr/bin/env python3
"""Invoice generator CLI (stdlib only).

Usage: invoice_gen.py INPUT.json [--format text|json] [--output FILE]
Exit codes: 0 ok, 2 unreadable/invalid input or validation errors.
"""
import argparse
import json
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def money(x):
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _is_num(v):
    return isinstance(v, Decimal)


def load_json(text):
    """Parse JSON with all numbers as Decimal (no float)."""
    return json.loads(text, parse_float=Decimal, parse_int=Decimal,
                      parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


def validate(inv):
    """Return a list of error strings (empty if valid), covering every defect."""
    errors = []
    if not isinstance(inv, dict):
        return ["invoice: must be a JSON object"]

    cust = inv.get("customer")
    if not isinstance(cust, dict):
        errors.append("customer: required object")
    else:
        name = cust.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append("customer.name: required non-empty string")
        for k in ("email", "address"):
            if k in cust and cust[k] is not None and not isinstance(cust[k], str):
                errors.append("customer.%s: must be a string" % k)

    items = inv.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items: required non-empty list")
    else:
        for i, it in enumerate(items):
            p = "items[%d]" % i
            if not isinstance(it, dict):
                errors.append("%s: must be an object" % p)
                continue
            d = it.get("description")
            if not isinstance(d, str) or not d.strip():
                errors.append("%s.description: required non-empty string" % p)
            q = it.get("quantity")
            if not _is_num(q) or q <= 0:
                errors.append("%s.quantity: must be a number > 0" % p)
            u = it.get("unit_price")
            if not _is_num(u) or u < 0:
                errors.append("%s.unit_price: must be a number >= 0" % p)

    t = inv.get("tax_rate")
    if not _is_num(t) or t < 0 or t > HUNDRED:
        errors.append("tax_rate: must be a number between 0 and 100")

    disc = inv.get("discount")
    if disc is not None:
        if not isinstance(disc, dict):
            errors.append("discount: must be an object {type, value}")
        else:
            dt, dv = disc.get("type"), disc.get("value")
            if dt not in ("percent", "fixed"):
                errors.append("discount.type: must be 'percent' or 'fixed'")
            if not _is_num(dv) or dv < 0:
                errors.append("discount.value: must be a number >= 0")
            elif dt == "percent" and dv > HUNDRED:
                errors.append("discount.value: percent must be <= 100")
            elif dt == "fixed" and not errors_in_items(errors):
                sub = sum((money(Decimal(it["quantity"]) * it["unit_price"])
                           for it in items), Decimal(0))
                if dv > sub:
                    errors.append("discount.value: fixed discount exceeds subtotal")
    return errors


def errors_in_items(errors):
    return any(e.startswith("items") for e in errors)


def compute(inv):
    """Compute amounts for a valid invoice. All amounts are Decimal cents."""
    lines = []
    for it in inv["items"]:
        total = money(it["quantity"] * it["unit_price"])
        lines.append({"description": it["description"], "quantity": it["quantity"],
                      "unit_price": it["unit_price"], "line_total": total})
    subtotal = sum((l["line_total"] for l in lines), Decimal(0))
    disc = inv.get("discount")
    if not disc:
        discount = Decimal("0.00")
    elif disc["type"] == "percent":
        discount = money(subtotal * disc["value"] / HUNDRED)
    else:
        discount = money(disc["value"])
    taxable = subtotal - discount
    tax = money(taxable * inv["tax_rate"] / HUNDRED)
    return {"customer": inv["customer"], "items": lines, "tax_rate": inv["tax_rate"],
            "subtotal": money(subtotal), "discount": discount, "tax": tax,
            "total": money(taxable + tax)}


def price(d):
    """Unit price: at least two decimals, keeping extra precision if present."""
    return format(d, "f") if d != money(d) else str(money(d))


def _num(d):
    return format(d.normalize(), "f") if d == d.to_integral() else format(d, "f")


def format_text(r):
    c = r["customer"]
    out = ["INVOICE", "=" * 60, "Customer: %s" % c["name"]]
    for k in ("email", "address"):
        if c.get(k):
            out.append("          %s" % c[k])
    out += ["-" * 60, "%-28s %8s %10s %11s" % ("Description", "Qty", "Unit", "Total"),
            "-" * 60]
    for l in r["items"]:
        out.append("%-28s %8s %10s %11s" % (l["description"][:28], _num(l["quantity"]),
                                            price(l["unit_price"]), l["line_total"]))
    out.append("-" * 60)
    w = 49
    out.append("%-*s %10s" % (w, "Subtotal:", r["subtotal"]))
    out.append("%-*s %10s" % (w, "Discount:", "-%s" % r["discount"]))
    out.append("%-*s %10s" % (w, "Tax (%s%%):" % _num(r["tax_rate"]), r["tax"]))
    out.append("%-*s %10s" % (w, "TOTAL:", r["total"]))
    return "\n".join(out) + "\n"


def to_json(r):
    c = r["customer"]
    doc = {
        "customer": {k: v for k, v in c.items() if isinstance(v, str)},
        "items": [{"description": l["description"], "quantity": _num(l["quantity"]),
                   "unit_price": price(l["unit_price"]),
                   "line_total": str(l["line_total"])} for l in r["items"]],
        "tax_rate": _num(r["tax_rate"]),
        "subtotal": str(r["subtotal"]), "discount": str(r["discount"]),
        "tax": str(r["tax"]), "total": str(r["total"]),
    }
    return json.dumps(doc, indent=2) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an invoice from JSON.")
    ap.add_argument("input")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--output")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        with open(args.input, encoding="utf-8") as f:
            inv = load_json(f.read())
    except (OSError, ValueError) as e:
        print("error: cannot read %s: %s" % (args.input, e), file=sys.stderr)
        return 2
    errors = validate(inv)
    if errors:
        print("%d validation error(s):" % len(errors), file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 2
    r = compute(inv)
    text = format_text(r) if args.format == "text" else to_json(r)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            print("error: cannot write %s: %s" % (args.output, e), file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
