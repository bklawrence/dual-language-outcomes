#!/usr/bin/env python3
"""Validate source scope and preservation for the six-state structural batch."""
from pathlib import Path

from dl_outcomes.validation import load
from dl_outcomes.western_plains_review import audit_errors


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    _, tables = load(root)
    errors = audit_errors(root, tables)
    if errors:
        raise SystemExit('\n'.join(errors))
    print('PASS: UT/CO/NM/AZ/NE/KS source scope, 650 reviewed keys, prior identities and assessment outputs preserved.')
