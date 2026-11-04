#!/usr/bin/env python3
"""Check preserved research, structural scope, deferred assessments and review views."""
from pathlib import Path
from dl_outcomes.structural import generate_report

if __name__ == '__main__':
    result = generate_report(Path(__file__).resolve().parents[1],check=True)
    print('PASS: structural research integrated for ' + ', '.join(result['states_with_integrated_program_evidence']) + '; existing assessment outputs unchanged.')
