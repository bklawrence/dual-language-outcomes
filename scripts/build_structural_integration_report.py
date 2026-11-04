#!/usr/bin/env python3
"""Generate review views without collecting new state or proficiency data."""
import json
from pathlib import Path
from dl_outcomes.structural import generate_report

if __name__ == '__main__':
    result = generate_report(Path(__file__).resolve().parents[1])
    print(json.dumps(result,indent=2))
