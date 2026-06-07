import json

with open('coverage.json') as f:
    data = json.load(f)

total = data['totals']['percent_covered']
covered = data['totals']['covered_lines']
total_lines = data['totals']['num_statements']

print(f"Coverage: {total:.1f}%")
print(f"Lines: {covered}/{total_lines}")
print(f"Status: {'✓ PASS (>= 75%)' if total >= 75 else '✗ FAIL (< 75%)'}")

