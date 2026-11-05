"""Validate the user-researched historical Illinois snapshot and scoped corrections."""
from pathlib import Path

from dl_outcomes.illinois_history import audit_errors
from dl_outcomes.validation import load

root = Path(__file__).resolve().parents[1]
_, tables = load(root)
errors = audit_errors(root, tables)
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: 144 Illinois source rows, 2021–22 dates, historical identities, IPA/Urbana policies and preserved prior research')
