"""Check the six-state PA/MD/DE/NJ/NY/CT source selections and prior preservation."""
from pathlib import Path

from dl_outcomes.mid_atlantic_ct_review import audit_errors
from dl_outcomes.validation import load

root = Path(__file__).resolve().parents[1]
_, tables = load(root)
errors = audit_errors(root, tables)
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: PA/MD/DE/NJ/NY/CT sources, named roster rows, language/grade/date scope and preserved prior research')
