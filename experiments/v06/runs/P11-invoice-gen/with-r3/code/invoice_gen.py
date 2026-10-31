#!/usr/bin/env python3
"""Invoice generator: read invoice JSON, validate, compute totals, print text or JSON."""
import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def money(value):
    """Round half-up to cents."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _num(value):
    """Return Decimal for a JSON number (not bool), else None."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        return None
    try:
        d = Decimal(value) if not isinstance(value, Decimal) else value
    except InvalidOperation:
        return None
    return d if d.is_finite() else None


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def validate(inv):
    """Return a list of error strings (empty when valid). Reports all errors."""
    errors = []
    if not isinstance(inv, dict):
        return ["$: invoice must be a JSON object"]

    customer = inv.get("customer")
    if not isinstance(customer, dict):
        errors.append("customer: required object")
    else:
        if not _nonempty_str(customer.get("name")):
            errors.append("customer.name: required non-empty string")
        for key in ("email", "address"):
            if key in customer and not isinstance(customer[key], str):
                errors.append("customer.%s: must be a string" % key)

    for key in ("number", "date"):
        if key in inv and not isinstance(inv[key], str):
            errors.append("%s: must be a string" % key)

    items = inv.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items: required non-empty list")
    else:
        for i, item in enumerate(items):
            p = "items[%d]" % i
            if not isinstance(item, dict):
                errors.append("%s: must be an object" % p)
                continue
            if not _nonempty_str(item.get("description")):
                errors.append("%s.description: required non-empty string" % p)
            q = _num(item.get("quantity"))
            if q is None or q <= 0:
                errors.append("%s.quantity: must be a number greater than 0" % p)
            u = _num(item.get("unit_price"))
            if u is None or u < 0:
                errors.append("%s.unit_price: must be a number >= 0" % p)

    t = _num(inv.get("tax_rate"))
    if t is None or t < 0 or t > 100:
        errors.append("tax_rate: must be a number between 0 and 100")

    if inv.get("discount") is not None:
        errors.extend(_validate_discount(inv["discount"], inv.get("items")))
    return errors


def _validate_discount(d, items):
    if not isinstance(d, dict):
        return ["discount: must be an object {type, value}"]
    errors = []
    kind = d.get("type")
    v = _num(d.get("value"))
    if kind not in ("percent", "fixed"):
        errors.append("discount.type: must be 'percent' or 'fixed'")
    if v is None or v < 0:
        errors.append("discount.value: must be a number >= 0")
    elif kind == "percent" and v > 100:
        errors.append("discount.value: percent must be between 0 and 100")
    elif kind == "fixed":
        sub = _subtotal_or_none(items)
        if sub is not None and v > sub:
            errors.append("discount.value: fixed discount exceeds subtotal")
    return errors


def _subtotal_or_none(items):
    """Subtotal if all items are computable, else None."""
    if not isinstance(items, list) or not items:
        return None
    total = Decimal(0)
    for item in items:
        if not isinstance(item, dict):
            return None
        q, u = _num(item.get("quantity")), _num(item.get("unit_price"))
        if q is None or u is None or q <= 0 or u < 0:
            return None
        total += money(q * u)
    return total


def compute(inv):
    """Compute amounts for a valid invoice. Returns a dict of Decimals."""
    lines = []
    for item in inv["items"]:
        q, u = _num(item["quantity"]), _num(item["unit_price"])
        lines.append({"description": item["description"], "quantity": q,
                      "unit_price": u, "line_total": money(q * u)})
    subtotal = sum((l["line_total"] for l in lines), Decimal(0))
    discount = Decimal(0)
    d = inv.get("discount")
    if d:
        v = _num(d["value"])
        discount = money(subtotal * v / HUNDRED) if d["type"] == "percent" else money(v)
    discount = min(discount, subtotal)
    taxable = subtotal - discount
    tax = money(taxable * _num(inv["tax_rate"]) / HUNDRED)
    return {"lines": lines, "subtotal": subtotal, "discount": discount,
            "taxable": taxable, "tax": tax, "total": taxable + tax}


def _q(d):
    s = format(d.normalize(), "f")
    return s


def to_dict(inv, c):
    return {
        "number": inv.get("number"),
        "date": inv.get("date"),
        "customer": inv["customer"],
        "items": [{"description": l["description"], "quantity": _q(l["quantity"]),
                   "unit_price": str(money(l["unit_price"])),
                   "line_total": str(l["line_total"])} for l in c["lines"]],
        "subtotal": str(c["subtotal"]),
        "discount": str(c["discount"]),
        "tax_rate": _q(_num(inv["tax_rate"])),
        "tax": str(c["tax"]),
        "total": str(c["total"]),
    }


def render_text(inv, c):
    out = []
    title = "INVOICE" + (" #%s" % inv["number"] if inv.get("number") else "")
    out.append(title)
    if inv.get("date"):
        out.append("Date: %s" % inv["date"])
    cust = inv["customer"]
    out.append("Bill to: %s" % cust["name"])
    for key in ("email", "address"):
        if cust.get(key):
            out.append("         %s" % cust[key])
    out.append("")
    w = max([len(l["description"]) for l in c["lines"]] + [11])
    fmt = "%-{w}s %8s %12s %12s".format(w=w)
    out.append(fmt % ("Description", "Qty", "Unit price", "Total"))
    out.append("-" * (w + 35))
    for l in c["lines"]:
        out.append(fmt % (l["description"], _q(l["quantity"]),
                          "{:,}".format(money(l["unit_price"])), "{:,}".format(l["line_total"])))
    out.append("-" * (w + 35))
    rows = [("Subtotal", c["subtotal"])]
    if c["discount"]:
        rows.append(("Discount", -c["discount"]))
    rows.append(("Tax (%s%%)" % _q(_num(inv["tax_rate"])), c["tax"]))
    rows.append(("TOTAL", c["total"]))
    for label, amt in rows:
        out.append("%-*s %12s" % (w + 18, label, "{:,}".format(amt)))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an invoice from a JSON file.")
    ap.add_argument("file", help="invoice JSON file ('-' for stdin)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)  # usage errors exit 2

    try:
        if args.file == "-":
            raw = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8") as fh:
                raw = fh.read()
        inv = json.loads(raw, parse_float=Decimal, parse_constant=_reject_constant)
    except (OSError, UnicodeDecodeError) as e:
        print("error: cannot read %s: %s" % (args.file, e), file=sys.stderr)
        return 2
    except ValueError as e:
        print("error: invalid JSON: %s" % e, file=sys.stderr)
        return 2

    errors = validate(inv)
    if errors:
        print("Invalid invoice (%d error%s):" % (len(errors), "" if len(errors) == 1 else "s"),
              file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1

    c = compute(inv)
    if args.format == "json":
        print(json.dumps(to_dict(inv, c), indent=2))
    else:
        sys.stdout.write(render_text(inv, c))
    return 0


def _reject_constant(name):
    raise ValueError("non-finite number %s not allowed" % name)


if __name__ == "__main__":
    sys.exit(main())
