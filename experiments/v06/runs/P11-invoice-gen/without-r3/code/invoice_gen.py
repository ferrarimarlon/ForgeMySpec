#!/usr/bin/env python3
"""Invoice generator CLI.

Reads an invoice JSON file, validates it (reporting every error at once),
computes totals with exact decimal arithmetic and prints a text invoice or
exports JSON.

Input format:
    {
      "invoice_number": "INV-001",          optional
      "date": "2026-10-31",                 optional (YYYY-MM-DD)
      "currency": "$",                      optional symbol/code prefix, default "$"
      "customer": "Acme"                    or {"name": ..., "email": ..., "address": ...}
      "items": [{"description": "Widget", "quantity": 3, "unit_price": 9.99}],
      "tax_rate": 8.25,                     percent, 0-100
      "discount": {"type": "percent", "value": 10}   optional; type: percent|fixed
    }

Rounding: every money amount is rounded half-up to cents. Line totals are
rounded first, the subtotal is their sum, the discount is rounded, and tax is
computed on (subtotal - discount) and rounded once.

Exit codes: 0 ok, 1 invalid invoice, 2 unreadable file / bad JSON / bad usage.
"""
import argparse
import json
import sys
from datetime import date as _date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _price(u):
    """Keep sub-cent unit prices exact (shown as given); otherwise 2 decimals."""
    return u if u.as_tuple().exponent < -2 else u.quantize(CENT)


def _is_num(v):
    return isinstance(v, Decimal) and v.is_finite()


def _nonempty_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate(data):
    """Return a list of error strings (empty if the invoice is valid)."""
    errors = []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"]

    # customer
    cust = data.get("customer")
    if cust is None:
        errors.append("customer: required")
    elif isinstance(cust, str):
        if not cust.strip():
            errors.append("customer: must not be empty")
    elif isinstance(cust, dict):
        if not _nonempty_str(cust.get("name")):
            errors.append("customer.name: required non-empty string")
        for key in ("email", "address"):
            if key in cust and not isinstance(cust[key], str):
                errors.append(f"customer.{key}: must be a string")
    else:
        errors.append("customer: must be a string or an object with a name")

    # optional metadata
    if "invoice_number" in data and not (
        _nonempty_str(data["invoice_number"]) or _is_num(data["invoice_number"])
    ):
        errors.append("invoice_number: must be a non-empty string")
    if "date" in data:
        d = data["date"]
        try:
            if not isinstance(d, str):
                raise ValueError
            _date.fromisoformat(d)
        except ValueError:
            errors.append("date: must be a YYYY-MM-DD string")
    if "currency" in data and not _nonempty_str(data["currency"]):
        errors.append("currency: must be a non-empty string")

    # items
    items = data.get("items")
    items_ok = True
    if items is None:
        errors.append("items: required")
        items_ok = False
    elif not isinstance(items, list):
        errors.append("items: must be a list")
        items_ok = False
    elif not items:
        errors.append("items: must contain at least one item")
        items_ok = False
    else:
        for i, it in enumerate(items, 1):
            p = f"items[{i}]"
            if not isinstance(it, dict):
                errors.append(f"{p}: must be an object")
                items_ok = False
                continue
            if not _nonempty_str(it.get("description")):
                errors.append(f"{p}.description: required non-empty string")
            q = it.get("quantity")
            if q is None:
                errors.append(f"{p}.quantity: required")
                items_ok = False
            elif not _is_num(q) or q <= 0:
                errors.append(f"{p}.quantity: must be a number greater than 0")
                items_ok = False
            u = it.get("unit_price")
            if u is None:
                errors.append(f"{p}.unit_price: required")
                items_ok = False
            elif not _is_num(u) or u < 0:
                errors.append(f"{p}.unit_price: must be a number >= 0")
                items_ok = False

    # tax rate
    tr = data.get("tax_rate")
    if tr is None:
        errors.append("tax_rate: required (percent, use 0 for none)")
    elif not _is_num(tr) or not (0 <= tr <= 100):
        errors.append("tax_rate: must be a number between 0 and 100 (percent)")

    # discount
    disc = data.get("discount")
    if disc is not None:
        if not isinstance(disc, dict):
            errors.append('discount: must be an object like {"type": "percent", "value": 10}')
        else:
            dtype, dval = disc.get("type"), disc.get("value")
            if dtype not in ("percent", "fixed"):
                errors.append('discount.type: must be "percent" or "fixed"')
            if not _is_num(dval) or dval < 0:
                errors.append("discount.value: must be a number >= 0")
            elif dtype == "percent" and dval > 100:
                errors.append("discount.value: percent must be <= 100")
            elif dtype == "fixed" and items_ok:
                sub = sum(
                    (money(it["quantity"] * it["unit_price"]) for it in items),
                    Decimal(0),
                )
                if money(dval) > sub:
                    errors.append(
                        f"discount.value: fixed discount ({money(dval)}) exceeds subtotal ({sub})"
                    )
    return errors


def compute(data):
    """Compute all amounts for a validated invoice."""
    lines = []
    for it in data["items"]:
        lines.append(
            {
                "description": it["description"],
                "quantity": it["quantity"],
                "unit_price": _price(it["unit_price"]),
                "total": money(it["quantity"] * it["unit_price"]),
            }
        )
    subtotal = sum((l["total"] for l in lines), Decimal(0))

    disc = data.get("discount")
    if disc and disc["type"] == "percent":
        discount = money(subtotal * disc["value"] / 100)
    elif disc:
        discount = money(disc["value"])
    else:
        discount = Decimal(0)
    discount = money(discount)

    taxable = subtotal - discount
    tax = money(taxable * data["tax_rate"] / 100)
    return {
        "lines": lines,
        "subtotal": subtotal,
        "discount": discount,
        "taxable": taxable,
        "tax": tax,
        "total": taxable + tax,
    }


def _qty(q):
    s = format(q.normalize(), "f")
    return s


def _pct(d):
    return format(d.normalize(), "f")


def _customer(data):
    c = data["customer"]
    return {"name": c} if isinstance(c, str) else c


def build_result(data):
    """Build the JSON-serialisable result (money as 2-decimal strings)."""
    r = compute(data)
    disc = data.get("discount")
    out = {
        "invoice_number": str(data["invoice_number"]) if "invoice_number" in data else None,
        "date": data.get("date"),
        "currency": data.get("currency", "$"),
        "customer": _customer(data),
        "items": [
            {
                "description": l["description"],
                "quantity": _qty(l["quantity"]),
                "unit_price": format(l["unit_price"], "f"),
                "total": str(l["total"]),
            }
            for l in r["lines"]
        ],
        "subtotal": str(r["subtotal"]),
        "discount": (
            {"type": disc["type"], "value": _pct(disc["value"]), "amount": str(r["discount"])}
            if disc
            else None
        ),
        "tax_rate": _pct(data["tax_rate"]),
        "tax": str(r["tax"]),
        "total": str(r["total"]),
    }
    return out


def _group(s):
    """Add thousands separators to a 2-decimal money string."""
    neg = s.startswith("-")
    whole, frac = s.lstrip("-").split(".")
    return ("-" if neg else "") + f"{int(whole):,}.{frac}"


def render_text(data):
    r = compute(data)
    cur = data.get("currency", "$")
    fmt = lambda d: f"{cur}{_group(format(d, 'f'))}"
    cust = _customer(data)
    disc = data.get("discount")

    head = ["INVOICE" + (f" {data['invoice_number']}" if "invoice_number" in data else "")]
    if "date" in data:
        head.append(f"Date: {data['date']}")
    head.append(f"Bill to: {cust['name']}")
    for k in ("email", "address"):
        if cust.get(k):
            head.append(f"         {cust[k]}")

    rows = [
        (l["description"], _qty(l["quantity"]), fmt(l["unit_price"]), fmt(l["total"]))
        for l in r["lines"]
    ]
    hdr = ("Description", "Qty", "Unit Price", "Total")
    wd = max(len(x[0]) for x in rows + [hdr])
    wq = max(len(x[1]) for x in rows + [hdr])
    wu = max(len(x[2]) for x in rows + [hdr])
    wt = max(len(x[3]) for x in rows + [hdr])

    def row(a, b, c, d):
        return f"{a:<{wd}}  {b:>{wq}}  {c:>{wu}}  {d:>{wt}}"

    width = wd + wq + wu + wt + 6
    out = head + ["", row(*hdr), "-" * width]
    out += [row(*x) for x in rows]
    out.append("-" * width)

    summary = [("Subtotal", fmt(r["subtotal"]))]
    if disc:
        label = f"Discount ({_pct(disc['value'])}%)" if disc["type"] == "percent" else "Discount"
        summary.append((label, "-" + fmt(r["discount"])))
    summary.append((f"Tax ({_pct(data['tax_rate'])}%)", fmt(r["tax"])))
    summary.append(("TOTAL", fmt(r["total"])))
    ws = max(len(v) for _, v in summary)
    for k, v in summary:
        out.append(f"{k:>{width - ws - 2}}  {v:>{ws}}")
    return "\n".join(out)


def load(path):
    # Parse numbers as Decimal so values like 0.1 or 19.995 stay exact.
    kw = dict(parse_float=Decimal, parse_int=Decimal, parse_constant=_reject_constant)
    if path == "-":
        return json.load(sys.stdin, **kw)
    with open(path, encoding="utf-8") as f:
        return json.load(f, **kw)


def _reject_constant(name):
    raise ValueError(f"invalid number {name}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate an invoice from a JSON file.")
    ap.add_argument("file", help="invoice JSON file, or - for stdin")
    ap.add_argument("-f", "--format", choices=("text", "json"), default="text")
    ap.add_argument("-o", "--output", help="write to this file instead of stdout")
    args = ap.parse_args(argv)

    try:
        data = load(args.file)
    except OSError as e:
        print(f"error: cannot read {args.file}: {e.strerror or e}", file=sys.stderr)
        return 2
    except ValueError as e:  # includes JSONDecodeError and UnicodeDecodeError
        print(f"error: invalid JSON in {args.file}: {e}", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        print(f"Invalid invoice: {len(errors)} error(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if args.format == "json":
        text = json.dumps(build_result(data), indent=2, ensure_ascii=False)
    else:
        text = render_text(data)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError as e:
            print(f"error: cannot write {args.output}: {e.strerror or e}", file=sys.stderr)
            return 2
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
