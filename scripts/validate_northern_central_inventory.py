"""Validate the seven-state source boundaries and preservation checks."""
from pathlib import Path
from dl_outcomes.northern_central_review import audit_errors
from dl_outcomes.validation import load

root = Path(__file__).resolve().parents[1]
_, tables = load(root)
errors = audit_errors(root, tables)
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: ND/SD/MN/IA/MO/AK/HI source scopes, reference years and preserved prior work')
