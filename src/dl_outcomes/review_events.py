"""Dated, cited changes to operation at a particular program site."""
from collections import defaultdict
import json

ATTRIBUTE = 'hand_coded_program_event'
KINDS = {'ended', 'moved', 'operating'}


def event_index(tables):
    events = [json.loads(c['reported_value']) for c in tables['evidence_claims'] if c['attribute'] == ATTRIBUTE]
    # Revising the same dated review corrects that fact. A later reference-year
    # observation or a different kind of event retains the previous history.
    superseded = set()
    by_review = {e['review_id']: e for e in events}
    for e in events:
        old = by_review.get(e.get('supersedes_review_id'))
        if old and old['kind'] == e['kind'] and old['reference_year'] == e['reference_year']:
            superseded.add(old['review_id'])
    result = defaultdict(list)
    for e in events:
        if e['review_id'] not in superseded:
            result[e['site_id']].append(e)
    return result


def event_at(events, year):
    candidates = [e for e in events if e['first_school_year'] <= year]
    return max(candidates, key=lambda e: (e['first_school_year'], e['submitted_at'],
               e.get('issue_number', 0), e.get('batch_record_index', 0), e['review_id']), default=None)
