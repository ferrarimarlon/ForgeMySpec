#!/usr/bin/env python3
"""Invoice Generator — WITHOUT framework. Direct implementation."""
import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("invoice")
parser.add_argument("--output")
args = parser.parse_args()

try:
    data = json.load(open(args.invoice))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr); sys.exit(1)

# Validate (stop at first error per category — missing spec detail)
errors = []
for f in ["client", "items", "tax_rate", "discount"]:
    if f not in data: errors.append(f"Missing: {f}")

if "tax_rate" in data and not (0 <= data["tax_rate"] <= 100):
    errors.append("tax_rate out of range")
if "discount" in data and not (0 <= data["discount"] <= 100):
    errors.append("discount out of range")

if "items" in data:
    for i, item in enumerate(data["items"]):
        if item.get("qty", 0) <= 0: errors.append(f"Item {i}: qty must be > 0")
        if item.get("unit_price", -1) < 0: errors.append(f"Item {i}: unit_price must be >= 0")

if errors:
    print("Validation errors:", file=sys.stderr)
    for e in errors: print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

# Compute
subtotal = sum(item["qty"] * item["unit_price"] for item in data["items"])
subtotal = round(subtotal, 2)
discount_amt = round(subtotal * data["discount"] / 100, 2)
taxable = round(subtotal - discount_amt, 2)
tax_amt = round(taxable * data["tax_rate"] / 100, 2)
total = round(taxable + tax_amt, 2)

# Print invoice
print("=" * 50)
print("INVOICE")
print(f"Client: {data['client']}")
print("-" * 50)
for item in data["items"]:
    line_total = round(item["qty"] * item["unit_price"], 2)
    print(f"  {item.get('description',''):<25} {item['qty']} x ${item['unit_price']:.2f} = ${line_total:.2f}")
print("-" * 50)
print(f"{'Subtotal:':>40} ${subtotal:.2f}")
print(f"{'Discount (' + str(data['discount']) + '%):':>40} -${discount_amt:.2f}")
print(f"{'Taxable:':>40} ${taxable:.2f}")
print(f"{'Tax (' + str(data['tax_rate']) + '%):':>40} ${tax_amt:.2f}")
print("=" * 50)
print(f"{'TOTAL:':>40} ${total:.2f}")

result = {
    "client": data["client"],
    "subtotal": subtotal,
    "discount_amount": discount_amt,
    "taxable_amount": taxable,
    "tax_amount": tax_amt,
    "total": total
}
if args.output:
    json.dump(result, open(args.output, "w"), indent=2)
    print(f"\nJSON saved to {args.output}")
else:
    print("\n" + json.dumps(result, indent=2))
