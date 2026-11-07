"""Public review totals credited to the researcher named in each journal entry."""
from collections import defaultdict


def leaderboard(records, schools):
    groups={};seen=set()
    for r in records:
        if r['review_id'] in seen:continue
        seen.add(r['review_id'])
        if not (r.get('changes') or r.get('program_event') or any((r.get(k) or '').strip() for k in ['evidence_url','notes','source_quote'])):
            continue
        name=' '.join(r['reviewer'].split());key=name.casefold()
        g=groups.setdefault(key,dict(reviewer=name,reviews=0,school_ids=set(),states=set(),batch_ids=set(),evidence_only=0,program_events=0))
        g['reviews']+=1;g['school_ids'].add(r['school_id']);g['batch_ids'].add(r['batch_id'])
        g['states'].add(schools[r['school_id']]['state_code'])
        g['evidence_only']+=not r.get('changes') and not r.get('program_event')
        g['program_events']+=bool(r.get('program_event'))
    rows=[dict(reviewer=g['reviewer'],reviews=g['reviews'],schools=len(g['school_ids']),states=len(g['states']),
               submissions=len(g['batch_ids']),evidence_only=g['evidence_only'],program_events=g['program_events']) for g in groups.values()]
    return sorted(rows,key=lambda r:(-r['reviews'],-r['schools'],r['reviewer'].casefold()))
