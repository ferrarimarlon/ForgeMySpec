#!/usr/bin/env python3
"""Invoice Generator CLI — WITH SpecForge framework.
Spec: spec.yaml v0.1
Rules: discount before tax, round at each step, report ALL validation errors.
"""
import argparse
import json
import sys
from typing import List


def load_invoice(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def validate_invoice(data: dict) -> List[str]:
    """Validate all fields. Returns list of all errors (does NOT stop at first)."""
    errors = []
    required_top = ["client", "items", "tax_rate", "discount"]
    for field in required_top:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if "tax_rate" in data:
        tr = data["tax_rate"]
        if not isinstance(tr, (int, float)) or not (0 <= tr <= 100):
            errors.append(f"tax_rate must be 0-100, got: {tr}")

    if "discount" in data:
        disc = data["discount"]
        if not isinstance(disc, (int, float)) or not (0 <= disc <= 100):
            errors.append(f"discount must be 0-100, got: {disc}")

    if "items" in data:
        if not isinstance(data["items"], list) or len(data["items"]) == 0:
            errors.append("items must be a non-empty list")
        else:
            for idx, item in enumerate(data["items"]):
                prefix = f"Item[{idx}]"
                if "description" not in item:
                    errors.append(f"{prefix}: missing 'description'")
                qty = item.get("qty")
                if qty is None:
                    errors.append(f"{prefix}: missing 'qty'")
                elif not isinstance(qty, (int, float)) or qty <= 0:
                    errors.append(f"{prefix}: qty must be > 0, got: {qty}")
                unit_price = item.get("unit_price")
                if unit_price is None:
                    errors.append(f"{prefix}: missing 'unit_price'")
                elif not isinstance(unit_price, (int, float)) or unit_price < 0:
                    errors.append(f"{prefix}: unit_price must be >= 0, got: {unit_price}")
    return errors


def compute_invoice(data: dict) -> dict:
    """Compute all financial values. Spec: discount before tax, round at each step."""
    items = []
    subtotal = 0.0
    for item in data["items"]:
        qty = item["qty"]
        up = item["unit_price"]
        item_total = round(qty * up, 2)
        subtotal = round(subtotal + item_total, 2)
        items.append({
            "description": item.get("description", ""),
            "qty": qty,
            "unit_price": up,
            "total": item_total,
        })

    discount_pct = data.get("discount", 0)
    tax_rate = data.get("tax_rate", 0)

    discount_amount = round(subtotal * discount_pct / 100, 2)
    taxable_amount = round(subtotal - discount_amount, 2)
    tax_amount = round(taxable_amount * tax_rate / 100, 2)
    total = round(taxable_amount + tax_amount, 2)

    return {
        "client": data.get("client", ""),
        "items": items,
        "subtotal": subtotal,
        "discount_pct": discount_pct,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total": total,
    }


def format_text_invoice(result: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("INVOICE")
    lines.append("=" * 60)
    lines.append(f"Client: {result['client']}")
    lines.append("")
    lines.append(f"{'Description':<30} {'Qty':>5} {'Unit Price':>10} {'Total':>10}")
    lines.append("-" * 60)
    for item in result["items"]:
        lines.append(
            f"{item['description']:<30} {item['qty']:>5} "
            f"${item['unit_price']:>9.2f} ${item['total']:>9.2f}"
        )
    lines.append("-" * 60)
    lines.append(f"{'Subtotal':>50} ${result['subtotal']:>9.2f}")
    if result["discount_pct"] > 0:
        lines.append(
            f"{'Discount (' + str(result['discount_pct']) + '%)':>50} "
            f"-${result['discount_amount']:>8.2f}"
        )
    lines.append(f"{'Taxable Amount':>50} ${result['taxable_amount']:>9.2f}")
    if result["tax_rate"] > 0:
        lines.append(
            f"{'Tax (' + str(result['tax_rate']) + '%)':>50} "
            f"${result['tax_amount']:>9.2f}"
        )
    lines.append("=" * 60)
    lines.append(f"{'TOTAL':>50} ${result['total']:>9.2f}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoice Generator CLI")
    parser.add_argument("invoice", help="Invoice JSON file")
    parser.add_argument("--output", help="Output JSON summary file (default: stdout)")
    parser.add_argument("--json-only", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    try:
        data = load_invoice(args.invoice)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading invoice: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_invoice(data)
    if errors:
        print(f"Validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    result = compute_invoice(data)

    if not args.json_only:
        print(format_text_invoice(result))
        print()

    summary = {k: v for k, v in result.items() if k != "items"}
    summary["item_count"] = len(result["items"])

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"JSON summary written to {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
