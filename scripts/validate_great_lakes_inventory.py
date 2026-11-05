"""Validate WI/MI/IL/IN source scopes and append-only Illinois expansion."""
from pathlib import Path

from dl_outcomes.great_lakes_review import audit_errors
from dl_outcomes.validation import load

root = Path(__file__).resolve().parents[1]
_, tables = load(root)
errors = audit_errors(root, tables)
if errors:
    raise SystemExit('\n'.join(errors))
print('PASS: WI/MI/IL/IN source scopes, roster reconciliation and preserved Illinois identities')
