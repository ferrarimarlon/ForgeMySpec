#!/usr/bin/env python3
"""Invoice generator CLI (stdlib only).

Input JSON:
{
  "invoice_number": "INV-001",            (optional)
  "date": "2026-10-31",                   (optional, YYYY-MM-DD)
  "customer": {"name": "Acme", "email": "a@b.c", "address": "..."},
  "items": [{"description": "Widget", "quantity": 2, "unit_price": 9.99}],
  "tax_rate": 8.25,                       (percent, 0-100)
  "discount": {"type": "percent", "value": 10}   (optional; or "fixed")
}

Calculation: line = round(qty * unit_price); subtotal = sum(lines);
discount = round(percent of subtotal) or fixed (capped at subtotal);
tax = round((subtotal - discount) * tax_rate / 100); total = taxable + tax.
All rounding is half-up to cents, using Decimal (never binary floats).
"""
import argparse
import datetime
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
HUNDRED = Decimal(100)


def money(x):
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _reject_constant(name):
    raise ValueError("invalid number %s" % name)


def _is_num(v):
    return isinstance(v, Decimal) and v.is_finite()


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate(data):
    """Return a list of error strings (empty if valid)."""
    errors = []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"]

    # customer
    cust = data.get("customer")
    if cust is None:
        errors.append("customer: missing")
    elif not isinstance(cust, dict):
        errors.append("customer: must be an object")
    else:
        if not _nonempty_str(cust.get("name")):
            errors.append("customer.name: required non-empty string")
        for k in ("email", "address"):
            if k in cust and cust[k] is not None and not isinstance(cust[k], str):
                errors.append("customer.%s: must be a string" % k)

    # optional header fields
    if "invoice_number" in data and not isinstance(data["invoice_number"], str):
        errors.append("invoice_number: must be a string")
    if "date" in data:
        d = data["date"]
        try:
            if not isinstance(d, str):
                raise ValueError
            datetime.date.fromisoformat(d)
        except ValueError:
            errors.append("date: must be a YYYY-MM-DD string")

    # items
    items = data.get("items")
    if items is None:
        errors.append("items: missing")
    elif not isinstance(items, list):
        errors.append("items: must be an array")
    elif not items:
        errors.append("items: must contain at least one item")
    else:
        for i, it in enumerate(items):
            p = "items[%d]" % i
            if not isinstance(it, dict):
                errors.append("%s: must be an object" % p)
                continue
            if not _nonempty_str(it.get("description")):
                errors.append("%s.description: required non-empty string" % p)
            q = it.get("quantity")
            if q is None:
                errors.append("%s.quantity: missing" % p)
            elif not _is_num(q):
                errors.append("%s.quantity: must be a number" % p)
            elif q <= 0:
                errors.append("%s.quantity: must be greater than 0" % p)
            u = it.get("unit_price")
            if u is None:
                errors.append("%s.unit_price: missing" % p)
            elif not _is_num(u):
                errors.append("%s.unit_price: must be a number" % p)
            elif u < 0:
                errors.append("%s.unit_price: must not be negative" % p)

    # tax rate
    t = data.get("tax_rate")
    if t is None:
        errors.append("tax_rate: missing")
    elif not _is_num(t):
        errors.append("tax_rate: must be a number (percent)")
    elif t < 0 or t > 100:
        errors.append("tax_rate: must be between 0 and 100 (percent)")

    # discount
    if data.get("discount") is not None:
        disc = data["discount"]
        if not isinstance(disc, dict):
            errors.append('discount: must be an object like {"type": "percent", "value": 10}')
        else:
            dt, dv = disc.get("type"), disc.get("value")
            if dt not in ("percent", "fixed"):
                errors.append('discount.type: must be "percent" or "fixed"')
            if not _is_num(dv):
                errors.append("discount.value: must be a number")
            elif dv < 0:
                errors.append("discount.value: must not be negative")
            elif dt == "percent" and dv > 100:
                errors.append("discount.value: percent must be at most 100")
    return errors


def compute(data):
    """Compute totals from validated data. Returns a dict of Decimals/strings."""
    lines = []
    for it in data["items"]:
        total = money(it["quantity"] * it["unit_price"])
        lines.append({
            "description": it["description"],
            "quantity": it["quantity"],
            "unit_price": it["unit_price"],
            "line_total": total,
        })
    subtotal = sum((l["line_total"] for l in lines), Decimal(0))

    discount = Decimal(0)
    disc = data.get("discount")
    if disc:
        if disc["type"] == "percent":
            discount = money(subtotal * disc["value"] / HUNDRED)
        else:
            discount = money(disc["value"])
        discount = min(discount, subtotal)
    taxable = subtotal - discount
    tax = money(taxable * data["tax_rate"] / HUNDRED)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "discount": discount,
        "taxable": taxable,
        "tax": tax,
        "total": taxable + tax,
    }


def _num_str(d):
    s = format(d.normalize(), "f")
    return s


def _price_str(d):
    """Unit price with thousands separators; at least 2 decimals, exact."""
    if d == money(d):
        return "{:,.2f}".format(d)
    return "{:,}".format(d.normalize())


def render_text(data, r):
    cust = data["customer"]
    out = []
    title = "INVOICE"
    if data.get("invoice_number") not in (None, ""):
        title += " " + str(data["invoice_number"])
    out.append(title)
    if data.get("date"):
        out.append("Date: %s" % data["date"])
    out.append("")
    out.append("Bill to: %s" % cust["name"])
    for k in ("email", "address"):
        if cust.get(k):
            out.append("         %s" % cust[k])
    out.append("")

    rows = [(l["description"], _num_str(l["quantity"]),
             _price_str(l["unit_price"]),
             "{:,.2f}".format(l["line_total"])) for l in r["lines"]]
    dw = max([len("Description")] + [len(x[0]) for x in rows])
    qw = max([len("Qty")] + [len(x[1]) for x in rows])
    uw = max([len("Unit Price")] + [len(x[2]) for x in rows])
    lw = max([len("Total"), len("{:,.2f}".format(r["total"])) + 1] + [len(x[3]) for x in rows])
    fmt = "%-{}s  %{}s  %{}s  %{}s".format(dw, qw, uw, lw)
    width = dw + qw + uw + lw + 6
    out.append(fmt % ("Description", "Qty", "Unit Price", "Total"))
    out.append("-" * width)
    for row in rows:
        out.append(fmt % row)
    out.append("-" * width)

    def summary(label, value):
        out.append("%s  %s" % (label.rjust(width - lw - 2), value.rjust(lw)))

    summary("Subtotal:", "{:,.2f}".format(r["subtotal"]))
    disc = data.get("discount")
    if r["discount"] > 0:
        label = "Discount"
        if disc["type"] == "percent":
            label += " (%s%%)" % _num_str(disc["value"])
        summary(label + ":", "-{:,.2f}".format(r["discount"]))
    summary("Tax (%s%%):" % _num_str(data["tax_rate"]), "{:,.2f}".format(r["tax"]))
    summary("TOTAL:", "{:,.2f}".format(r["total"]))
    return "\n".join(out) + "\n"


def render_json(data, r):
    def m(x):
        return str(x)  # Decimal already quantized -> "12.30"

    disc = data.get("discount")
    doc = {
        "invoice_number": data.get("invoice_number"),
        "date": data.get("date"),
        "customer": data["customer"],
        "items": [{
            "description": l["description"],
            "quantity": _num_str(l["quantity"]),
            "unit_price": _num_str(l["unit_price"]),
            "line_total": m(l["line_total"]),
        } for l in r["lines"]],
        "discount": ({"type": disc["type"], "value": _num_str(disc["value"])}
                     if disc else None),
        "tax_rate": _num_str(data["tax_rate"]),
        "subtotal": m(r["subtotal"]),
        "discount_amount": m(r["discount"]),
        "taxable_amount": m(r["taxable"]),
        "tax": m(r["tax"]),
        "total": m(r["total"]),
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def load(path):
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            with open(path, encoding="utf-8") as f:
                text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise SystemExit("error: cannot read %s: %s" % (path, e))
    try:
        return json.loads(text, parse_float=Decimal, parse_int=Decimal,
                          parse_constant=_reject_constant)
    except (ValueError, InvalidOperation) as e:
        raise SystemExit("error: invalid JSON in %s: %s" % (path, e))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an invoice from a JSON file.")
    ap.add_argument("input", help="invoice JSON file ('-' for stdin)")
    ap.add_argument("-f", "--format", choices=("text", "json"), default="text")
    ap.add_argument("-o", "--output", help="write to file instead of stdout")
    args = ap.parse_args(argv)

    data = load(args.input)
    errors = validate(data)
    if errors:
        sys.stderr.write("Invalid invoice (%d error%s):\n"
                         % (len(errors), "" if len(errors) == 1 else "s"))
        for e in errors:
            sys.stderr.write("  - %s\n" % e)
        return 1

    r = compute(data)
    text = render_text(data, r) if args.format == "text" else render_json(data, r)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            sys.stderr.write("error: cannot write %s: %s\n" % (args.output, e))
            return 2
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
