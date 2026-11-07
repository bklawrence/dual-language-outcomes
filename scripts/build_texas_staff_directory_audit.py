"""Freeze the Texas discovery/access audit; never assign models from search hits.

Usage: python scripts/build_texas_staff_directory_audit.py --cache CACHE
The cache is the public-page acquisition workspace, with mapped_schools.json,
grade-team-leads.json, and URL-hash metadata/text files. Only the separately
adjudicated observations.json supplies delivery decisions. This command does
not access the network or rebuild canonical data.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/registry/tx_staff_delivery_review_2026_11_07'


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        fields = list(rows[0]) if rows else []
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def public_text(cache, meta):
    key = meta['key'].replace('_browser', '.browser')
    path = cache / (key + '.txt')
    return path.read_text() if path.exists() else ''


def documents(cache):
    captures = []
    for path in sorted(cache.glob('*.json')):
        if len(path.stem) != 22 and not path.name.endswith('.browser.json'):
            continue
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or not value.get('url') or not value.get('key'):
            continue
        if any(host in urlsplit(value['url']).netloc for host in ('bing.com', 'google.com', 'mps.school')):
            continue  # Search results and Wisconsin controls are not Texas evidence.
        text = public_text(cache, value)
        if (value.get('status') == 'retrieved' and len(text) < 3500
                and re.search(r'Robot Challenge|Press and Hold|Access Denied|not a robot',
                              text + ' ' + value.get('title', ''), re.I)):
            value['status'] = 'access_blocked'
        captures.append(value)
    selected = {}
    for meta in sorted(captures, key=lambda m: m['key'].endswith('_browser')):
        if meta.get('status') == 'retrieved' or meta['url'] not in selected:
            selected[meta['url']] = meta
    return captures, selected


def campus_specific(school, meta, text):
    """A discovery check, not a manual identity adjudication or negative proof."""
    def words(value):
        return set(re.findall(r'[a-z]{3,}', value.lower())) - {
            'the', 'and', 'school', 'elementary', 'academy', 'middle', 'high',
            'staff', 'directory', 'dual', 'language', 'new', 'tech', 'preparatory',
        }
    wanted = words(school['school_name'])
    identity = ' '.join([meta.get('title', ''), *meta.get('headings', [])[:2], text[-2000:]])
    matched = wanted & words(identity)
    return bool(wanted and (wanted <= words(identity) or len(matched) >= 2))


def freeze(cache):
    schools = json.loads((cache / 'mapped_schools.json').read_text())
    children = json.loads((cache / 'grade-team-leads.json').read_text())
    observations = json.loads((BASE / 'observations.json').read_text())
    cases = json.loads((BASE / 'review_cases.json').read_text())
    sources = json.loads((BASE / 'sources.json').read_text())
    decisions = {f['school_id']: f for f in observations}
    review_cases = {c['school_id']: c for c in cases}
    captures, selected = documents(cache)
    archived = {s['sha256']: s['path'] for s in sources}
    rows = []
    vetted_leads = []
    for school in schools:
        sid = school['school_id']
        urls = list(dict.fromkeys(
            [lead['url'] for lead in school['staff_candidates']]
            + [lead['url'] for lead in children.get(sid, [])]))
        fact = decisions.get(sid)
        case = review_cases.get(sid)
        if fact or case:
            keys = (fact or case)['source_keys']
            urls += [s['url'] for s in sources if s['key'] in keys and s['url'] not in urls]
        attempts = [selected[u] for u in urls if u in selected]
        retrieved = [m for m in attempts if m.get('status') == 'retrieved']
        scoped = [m for m in retrieved if campus_specific(school, m, public_text(cache, m))]
        staff_text = [m for m in scoped if re.search(
            r'\bteacher\b|\bprincipal\b|\bTitles:|\bSelf Contained\b',
            public_text(cache, m), re.I)]
        home_urls = [h['url'] for h in school['campus_home_candidates']]
        home_retrieved = any(selected.get(u, {}).get('status') == 'retrieved' for u in home_urls)
        if fact:
            outcome = 'provisional_strand_from_parallel_academic_roles'
            note = fact['notes']
        elif case:
            outcome = 'ambiguous_followup_no_assignment'
            note = case['notes']
        elif staff_text:
            outcome = 'accessible_campus_matched_staff_material_no_reviewed_split'
            note = ('No qualifying split adjudicated in the accessible material. The campus match is automated; '
                    'pagination, images, linked documents and unlabelled roles can leave relevant evidence unseen. '
                    'This is not proof of absence and does not imply whole-school delivery.')
        elif retrieved:
            outcome = 'staff_lead_retrieved_scope_or_content_unresolved'
            note = ('A staff lead returned a page, but campus identity or usable staff content remains unresolved. '
                    'Some campus links redirect to district portals or display only navigation/search controls.')
        elif attempts:
            outcome = 'staff_lead_inaccessible'
            note = 'Staff leads failed to load or were blocked; no model inferred from access failure.'
        elif home_retrieved:
            outcome = 'campus_page_only_no_accessible_staff_lead'
            note = 'A candidate campus page loaded, but no staff material was successfully retrieved in this pass.'
        else:
            outcome = 'campus_link_or_access_unresolved'
            note = 'Official/state-directory and district-navigation discovery attempted; current campus link or access unresolved.'
        pagination = []
        for meta in retrieved:
            text = public_text(cache, meta)
            pagination += re.findall(r'showing\s+\d+\s*-\s*\d+\s+of\s+\d+|Jump to Page', text, re.I)
        rows.append(dict(
            school_id=sid, school_name=school['school_name'], district_id=school['district_id'],
            district_name=school['district_name'], school_level=school['school_level'],
            program_site_count=len(school['program_site_ids']),
            program_site_ids=' | '.join(school['program_site_ids']),
            official_web_url=school['official_web_url'],
            official_web_access_status=selected.get(school['official_web_url'], {}).get('status', 'no_url_or_capture'),
            district_root=school['district_root'],
            district_root_access_status=selected.get(school['district_root'], {}).get('status', 'no_url_or_capture'),
            campus_home_candidates=' | '.join(home_urls), staff_lead_urls=' | '.join(urls),
            staff_lead_urls_attempted=len(attempts), staff_lead_urls_retrieved=len(retrieved),
            campus_matched_staff_text_pages=len(staff_text),
            staff_access_outcomes=json.dumps(dict(Counter(m['status'] for m in attempts)), sort_keys=True),
            pagination_observed=' | '.join(sorted(set(pagination))),
            staff_entries_exhaustively_reviewed=0,
            audit_outcome=outcome,
            manually_adjudicated=int(bool(fact or case)),
            new_delivery_structure=fact['value'] if fact else '',
            new_delivery_verification_status=fact['verification_status'] if fact else '',
            reference_year='2025-26', source_school_year=fact['source_school_year'] if fact else '',
            source_capture_date=fact['source_capture_date'] if fact else '',
            notes=note,
        ))
        if fact or case:
            source = next(s for s in sources if s['key'] == (fact or case)['source_keys'][0])
            vetted_leads.append(dict(school_id=sid, url=source['url'], label='Staff directory',
                locator=(fact or case).get('source_locator', 'Staff-directory follow-up'),
                excerpt=(fact or case)['notes'][:700], manually_checked_campus_identity=True))

    write_csv(BASE / 'campus_audit.csv', rows)
    source_index = {s['key']:s for s in sources}
    write_csv(BASE / 'decisions.csv', [dict(
        school_id=f['school_id'], school_name=f['school_name'], district_name=f['district_names'],
        site_id=f['site_id'], program_id=f['program_id'], delivery_structure=f['value'],
        verification_status=f['verification_status'], reference_year=f['reference_year'],
        source_school_year=f['source_school_year'], source_capture_date=f['source_capture_date'],
        source_url=source_index[f['source_keys'][0]]['url'], delivery_grade_scope=f['delivery_grade_scope'],
        role_quotes=' | '.join(q['quote'] for q in f['source_quote_fragments']), notes=f['notes'],
    ) for f in observations])
    write_csv(BASE / 'review_cases.csv', [dict(c, source_keys=' | '.join(c['source_keys'])) for c in cases])
    write_json(BASE / 'vetted_staff_leads.json', vetted_leads)
    access = [dict(
        url=m['url'], final_url=m.get('final_url', ''), retrieved_at=m.get('retrieved_at', ''),
        access_status=m.get('status', ''), http_status=m.get('http_status', ''),
        capture_method=m.get('capture_method', 'public_HTTP_request'),
        archive_kind=m.get('archive_kind', ''), saved_body_sha256=m.get('sha256', ''),
        decoded_body_sha256=m.get('body_sha256', ''),
        repository_snapshot_path=archived.get(m.get('sha256'), ''),
        error=m.get('error', '') or m.get('navigation_error', ''),
        prior_attempt_count=len(m.get('previous_attempts', [])),
    ) for m in captures]
    write_csv(BASE / 'access_log.csv', access)
    # Mapping candidates are research leads, not silently accepted identities.
    (BASE / 'mapped_campus_leads.json.gz').write_bytes(gzip.compress(
        json.dumps(schools, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    targets = [{k: v for k, v in s.items() if k not in {'campus_home_candidates', 'staff_candidates'}} for s in schools]
    write_json(BASE / 'campus_targets.json', targets)
    summary = dict(
        research_date='2026-11-07', reference_year='2025-26',
        inventory_campuses=len(rows), inventory_districts=len({r['district_id'] for r in rows}),
        inventory_program_sites=sum(r['program_site_count'] for r in rows),
        campuses_with_staff_lead_attempts=sum(r['staff_lead_urls_attempted'] > 0 for r in rows),
        campuses_with_retrieved_staff_lead=sum(r['staff_lead_urls_retrieved'] > 0 for r in rows),
        campuses_with_automatically_matched_staff_text=sum(r['campus_matched_staff_text_pages'] > 0 for r in rows),
        campuses_with_manual_positive_or_ambiguous_review=sum(r['manually_adjudicated'] for r in rows),
        newly_inferred_strand_campuses=len(decisions), newly_inferred_strand_program_sites=len(observations),
        whole_school_assignments=0, ambiguous_review_campuses=len(cases),
        campuses_by_outcome=dict(Counter(r['audit_outcome'] for r in rows)),
        acquisition_captures=len(access), acquisition_access_outcomes=dict(Counter(r['access_status'] for r in access)),
        archived_review_sources=sum(s['research_use'] != 'campus_URL_discovery_only_not_program_evidence' for s in sources),
        archived_discovery_sources=sum(s['research_use'] == 'campus_URL_discovery_only_not_program_evidence' for s in sources),
        interpretation='All campuses received an inventory/discovery screen. Retrieved leads and automated campus matches are not equivalent to a complete staff roster or individual manual review. No uninformative, inaccessible, or ambiguous case is assigned a delivery model.',
        temporal_policy=json.loads((ROOT / 'config/research_migrations/tx_staff_delivery_review_2026_11_07.json').read_text())['temporal_policy'],
    )
    write_json(BASE / 'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    freeze(parser.parse_args().cache)
