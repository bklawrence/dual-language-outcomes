"""Append campus participation evidence without changing allocation or history."""
from collections import Counter, defaultdict
from hashlib import sha256
import gzip
import json
from pathlib import PurePosixPath

from .baseline import csv_text, json_text
from .baseline_selection import Selection
from .gap_pilot import add_scope
from .io import digest, record_id

CONFIG = 'config/research_migrations/delivery_scope_cleanup_2026_11_06.json'
DATASET = 'DELIVERY_SCOPE_CLEANUP_2026_11_06'
REVIEW = 'delivery_scope_review_observation'


def inputs(root):
    config = json.loads((root / CONFIG).read_text())
    base = root / config['base']
    files = {p.stem: json.loads(p.read_text()) for p in base.glob('*.json')}
    with gzip.open(base / 'original_keys.json.gz', 'rt') as stream:
        files['original_keys'] = json.load(stream)
    return config, files


def source_ids(files):
    return {s['key']: s.get('reuse_source_id') or record_id('source', DATASET, s['sha256'])
            for s in files['sources']}


def added_ids(files):
    """Identify only this migration's appended rows for preservation checks."""
    result = defaultdict(set)
    result['datasets'].add(DATASET)
    sources = source_ids(files)
    for source in files['sources']:
        if not source.get('reuse_source_id'):
            result['sources'].add(sources[source['key']])
    for fact in files['observations']:
        result['program_configurations'].add(record_id('configuration', DATASET, fact['fact_id']))
        sid = sources[fact['source_keys'][0]]
        for attribute, locator in [
            ('reviewed_record_reference_scope', fact['fact_id'] + ':reference_scope'),
            (REVIEW, fact['fact_id'] + ':review'),
            ('reviewed_structural_field_selection', fact['site_id'] + ':' + fact['reference_year'] + ':delivery_structure'),
        ]:
            result['evidence_claims'].add(record_id('claim', 'program', fact['program_id'], attribute, sid, locator))
    return result


def migrate(build):
    config, files = inputs(build.root)
    build.track_input(CONFIG)
    for path in sorted((build.root / config['base']).rglob('*')):
        if path.is_file():
            build.track_input(path)
    for path in files['preservation']['preserved_files']:
        build.track_input(path)
    build.dataset(DATASET, None, 'inventory', 'Reviewed whole-school versus strand delivery',
                  'repo:' + config['base'], notes=config['scope'])
    sources = {}
    existing = {r['source_id']: r for r in build.rows('sources')}
    for source in files['sources']:
        if source.get('reuse_source_id'):
            row = existing[source['reuse_source_id']]
            if row['sha256'] != source['sha256'] or row['snapshot_path'] != source['path']:
                raise ValueError('Reused delivery source does not match its archive: ' + source['key'])
            if digest(build.track_input(source['path'])) != source['sha256']:
                raise ValueError('Delivery source bytes changed: ' + source['key'])
            sources[source['key']] = row['source_id']
        else:
            sources[source['key']] = build.source_file(DATASET, source['path'], metadata=source['metadata_path'])
    sites = {r['site_id']: r for r in build.rows('program_sites')}
    schools = {r['school_id']: r for r in build.rows('schools')}
    for fact in files['observations']:
        site = sites[fact['site_id']]
        if (site['school_id'] != fact['school_id'] or site['program_id'] != fact['program_id']
                or schools[fact['school_id']]['state_code'] != fact['state']):
            raise ValueError('Delivery review crosses an existing school/programme identity')
        source = sources[fact['source_keys'][0]]
        cid = record_id('configuration', DATASET, fact['fact_id'])
        period = fact['evidence_period_raw']
        note = (fact['notes'] + ' Delivery scope: ' + fact['delivery_grade_scope']
                + '. Source locator: ' + fact['source_locator'] + '. Source quote: ' + fact['source_quote'])
        # Unknown defaults prevent this delivery-only observation from becoming
        # a new grade span, allocation model, programme type or population model.
        build.add('program_configurations', configuration_id=cid, site_id=fact['site_id'],
                  school_year=fact['source_school_year'], grade_scope='not_reported',
                  population_model='unknown', delivery_structure=fact['value'],
                  program_kind='reviewed_structural_selection_with_separate_source_dates',
                  evidence_period_raw=period, verification_status='documented', source_id=source,
                  source_locator=fact['fact_id'], notes=note)
        add_scope(build, fact, 'program_configurations', [cid], source)
        metadata = dict(fact, canonical_evidence_ids=[cid],
                        supporting_source_ids=[sources[key] for key in fact['source_keys']],
                        temporal_interpretation=config['temporal_policy'])
        build.claim('program', fact['program_id'], REVIEW, json_text(metadata), source,
                    fact['fact_id'] + ':review', year=fact['reference_year'], status='metadata_only',
                    method=fact['method'], notes='Campus scope, grade coverage and reference applicability retained separately.')
        value = dict(site_id=fact['site_id'], program_id=fact['program_id'], school_id=fact['school_id'],
                     selection_year=fact['reference_year'], variable='delivery_structure', evidence_ids=[cid],
                     reason='Manual campus delivery review; earlier source observations retained. ' + fact['notes'])
        build.claim('program', fact['program_id'], 'reviewed_structural_field_selection',
                    json_text(value), source, fact['site_id'] + ':' + fact['reference_year'] + ':delivery_structure',
                    year=fact['reference_year'], status='metadata_only', method='field_specific_reference_selection',
                    notes=config['temporal_policy'])
    build.notes.append(config['scope'] + ' ' + config['temporal_policy'])


def row_fingerprint(rows, definition):
    keys = definition['x-primary-key']
    rows = sorted(rows, key=lambda r: tuple(str(r[k]) for k in keys))
    return sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def prior_tables(tables, files, schema):
    original = {name: {tuple(k) for k in keys} for name, keys in files['original_keys'].items()}
    return {name: [r for r in rows if tuple(r[k] for k in schema['$defs'][name]['x-primary-key']) in original[name]]
            for name, rows in tables.items()}


def review_projection(tables, files, schema):
    """Audit this pass independently of evidence appended by future passes."""
    prior = prior_tables(tables, files, schema)
    added = added_ids(files)
    for name, rows in tables.items():
        key = schema['$defs'][name]['x-primary-key'][0]
        prior[name] += [r for r in rows if r[key] in added[name]]
    return prior


def audit_errors(root, tables):
    from .contracts import catalog
    config, files = inputs(root)
    errors = []
    schema = catalog()
    prior = prior_tables(tables, files, schema)
    for name, receipt in files['preservation']['canonical_tables'].items():
        # Coverage is a derived inventory availability view; assessment and
        # demographic observations themselves remain byte-for-byte unchanged.
        if name == 'coverage':
            continue
        if len(prior[name]) != receipt['rows'] or row_fingerprint(prior[name], schema['$defs'][name]) != receipt['sha256']:
            errors.append('Delivery review changed a pre-existing canonical row: ' + name)
    for path, expected in files['preservation']['preserved_files'].items():
        if digest(root / path) != expected:
            errors.append('Delivery review changed a frozen baseline or archived report: ' + path)
    sources = {s['key']: s for s in files['sources']}
    cohort = {r['site_id']: r for r in files['cohort']}
    rules = json.loads((root / 'data/baselines/national_structural_v1/rules.json').read_text())
    selection = Selection(review_projection(tables, files, schema), rules)
    sites = {r['site_id']: r for r in tables['program_sites']}
    for fact in files['observations']:
        before = cohort.get(fact['site_id'])
        if not before or before['school_id'] != fact['school_id'] or before['program_id'] != fact['program_id']:
            errors.append('Delivery decision is outside the fixed allocation-bearing cohort: ' + fact['fact_id'])
        if fact['earliest_reviewed_selection_year'] != config['reference_year'] or fact['reference_year'] != config['reference_year']:
            errors.append('Delivery reference-use bound changed: ' + fact['fact_id'])
        if fact['latest_reviewed_selection_year'] != config['reference_year']:
            errors.append('Delivery review extends beyond its reviewed year: ' + fact['fact_id'])
        if fact['source_school_year'] and fact['source_school_year'] > fact['reference_year']:
            errors.append('Delivery decision backdates a source year: ' + fact['fact_id'])
        text = ' '.join((root / sources[fact['source_keys'][0]]['extraction_path']).read_text().split())
        if ' '.join(fact['source_quote'].split()) not in text:
            errors.append('Delivery quote not present in its saved extraction: ' + fact['fact_id'])
        field, _ = selection.select_field(sites[fact['site_id']], 'delivery_structure', config['reference_year'])
        if field['value_status'] != 'documented' or json.loads(field['value_json']) != [fact['value']]:
            errors.append('Delivery review is not the selected current field: ' + fact['fact_id'])
    # The delivery-only configurations must not change selections in any other
    # field, including their source attribution or temporal interpretation.
    for before in files['before_non_delivery_fields']:
        site = sites[before['site_id']]
        variable = before['variable']; year = before['selection_year']
        if variable == 'reference_operation':
            after, _ = selection.operation_field(site, year)
        elif variable == 'elementary_allocation_model':
            grades, _ = selection.select_field(site, 'programme_grade_scope', year)
            after, _ = selection.select_allocations(site, year, before['_review_school_level'], json.loads(grades['value_json']))
        else:
            after, _ = selection.select_field(site, variable, year)
        expected = {k: v for k, v in before.items() if k != '_review_school_level'}
        if after != expected:
            errors.append('Delivery-only review changed another selected field: ' + variable + '/' + site['site_id'])
    return errors


def render_reports(root, tables):
    config, files = inputs(root)
    errors = audit_errors(root, tables)
    if errors:
        raise ValueError('\n'.join(errors))
    rules = json.loads((root / 'data/baselines/national_structural_v1/rules.json').read_text())
    selection = Selection(tables, rules)
    sites = {r['site_id']: r for r in tables['program_sites']}
    decisions = {f['site_id']: f for f in files['observations']}
    sources = {s['key']: s for s in files['sources']}
    rows = []
    for before in files['cohort']:
        field, _ = selection.select_field(sites[before['site_id']], 'delivery_structure', config['reference_year'])
        fact = decisions.get(before['site_id'])
        rows.append(dict(before, reference_year=config['reference_year'],
                         after_delivery_structure=' | '.join(json.loads(field['value_json'])),
                         after_delivery_structure_status=field['value_status'],
                         after_delivery_temporal_status=field['temporal_status'],
                         selected_evidence_ids=field['selected_evidence_ids'], selected_source_ids=field['selected_source_ids'],
                         reviewed_in_this_pass=int(bool(fact)), source_quote=fact['source_quote'] if fact else '',
                         source_locator=fact['source_locator'] if fact else '',
                         delivery_grade_scope=fact['delivery_grade_scope'] if fact else '',
                         source_school_year=fact['source_school_year'] if fact else '',
                         source_publication_date=fact.get('source_publication_date') if fact else '',
                         review_method=fact['method'] if fact else '',
                         notes=fact['notes'] if fact else '',
                         source_urls=' | '.join(sources[k]['url'] for k in fact['source_keys']) if fact else ''))
    by_school = defaultdict(list)
    for row in rows:
        by_school[row['school_id']].append(row)
    school_rows = []
    for sid, group in sorted(by_school.items()):
        row = group[0]
        school_rows.append(dict(school_id=sid, state_code=row['state_code'], school_name=row['school_name'],
            district_names=row['district_names'], allocation_bearing_programme_sites=len(group),
            before_all_allocated_sites_documented=int(all(r['delivery_structure_status']=='documented' for r in group)),
            after_all_allocated_sites_documented=int(all(r['after_delivery_structure_status']=='documented' for r in group)),
            reviewed_in_this_pass=int(any(r['reviewed_in_this_pass'] for r in group)),
            delivery_values=' | '.join(sorted({r['after_delivery_structure'] for r in group if r['after_delivery_structure']}))))
    states = []
    for state in sorted({r['state_code'] for r in school_rows}):
        group = [r for r in school_rows if r['state_code']==state]
        b = sum(r['before_all_allocated_sites_documented'] for r in group)
        a = sum(r['after_all_allocated_sites_documented'] for r in group)
        states.append(dict(state_code=state, schools_with_allocation=len(group), before_documented_delivery=b,
                           after_documented_delivery=a, newly_documented=a-b,
                           after_delivery_coverage_pct=round(100*a/len(group), 2), remaining_not_fully_documented=len(group)-a))
    reviewed = [r for r in rows if r['reviewed_in_this_pass']]
    classified = {f['school_id']: f['value'] for f in files['observations']}
    before = sum(r['before_all_allocated_sites_documented'] for r in school_rows)
    after = sum(r['after_all_allocated_sites_documented'] for r in school_rows)
    summary = dict(research_date=config['research_date'], reference_year=config['reference_year'],
        allocated_programme_sites=len(rows), allocated_schools=len(school_rows),
        programme_site_decisions=len(reviewed), school_decisions=len(classified),
        school_decisions_by_value=dict(Counter(classified.values())),
        school_decisions_by_state=dict(Counter(r['state'] for r in {f['school_id']:f for f in files['observations']}.values())),
        before_schools_all_allocated_sites_documented=before, after_schools_all_allocated_sites_documented=after,
        before_delivery_coverage_pct=round(100*before/len(school_rows),2), after_delivery_coverage_pct=round(100*after/len(school_rows),2),
        remaining_schools_not_fully_documented=len(school_rows)-after, source_documents=len(sources),
        sources_reused=sum(bool(s.get('reuse_source_id')) for s in sources.values()),
        temporal_policy=config['temporal_policy'], screening=files['screening'],
        denominator='Existing live allocation-bearing elementary programme-site cohort, not all US DL schools. A school is fully documented here when every allocation-bearing site has documented delivery.',
        analysis_effect='Earlier 2024-25 and older proficiency selections are unchanged. Whole-school scope does not establish identified DL assessment participation or programme exposure for a tested cohort.',
        evidence_preservation='All pre-existing canonical evidence, identities, assessment/context tables, frozen baseline and prior reports retained.',
        audit_status='PASS')
    cases = [dict(c, source_urls=' | '.join(sources[k]['url'] for k in c['source_keys'])) for c in files['review_cases']]
    source_rows = [dict(key=s['key'], title=' '.join(s['title'].split()), url=s['url'], snapshot_path=s['path'], sha256=s['sha256'],
                        reuse_source_id=s.get('reuse_source_id'),
                        observations_supported=sum(s['key'] in f['source_keys'] for f in files['observations'])) for s in files['sources']]
    p = config['report_prefix']
    return {p+'.json': json_text(summary), p+'_decisions.csv': csv_text(reviewed),
            p+'_allocated_programmes.csv': csv_text(rows), p+'_schools.csv': csv_text(school_rows),
            p+'_by_state.csv': csv_text(states), p+'_remaining_queue.csv': csv_text([r for r in rows if r['after_delivery_structure_status']!='documented']),
            p+'_review_cases.csv': csv_text(cases), p+'_sources.csv': csv_text(source_rows)}, summary


def revise_report_paths(root, contents):
    config, files = inputs(root)
    previous = files['preservation']['preserved_files']
    revised = {}; aliases = {}
    for path, text in contents.items():
        target = path
        if path in previous and sha256(text.encode()).hexdigest() != previous[path]:
            target = config['revised_report_directory'] + '/' + PurePosixPath(path).name
            aliases[path] = target
        if target in revised:
            raise ValueError('Delivery report path collision: ' + target)
        revised[target] = text
    return revised, aliases
