"""Check school-specific NY allocation provenance and original-source conservation."""
from pathlib import Path

from dl_outcomes.ny_allocation_followup import audit_errors
from dl_outcomes.validation import load

root = Path(__file__).resolve().parents[1]
_, tables = load(root)
errors = audit_errors(root, tables)
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: all 200 original NY primary hosts, source conservation, grade scope and explicit inference')
