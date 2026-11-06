"""Validate the final five-state structural pass and preservation receipts."""
from pathlib import Path

from dl_outcomes.new_england_review import audit_errors
from dl_outcomes.validation import load

root = Path(__file__).resolve().parents[1]
_, tables = load(root)
errors = audit_errors(root, tables)
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: ME/MA/NH/RI/VT source rows, language/grade/date distinctions and prior research preservation')
