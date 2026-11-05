"""User-reviewed Texas model classifications, with explicit inference provenance."""
from collections import Counter, defaultdict
import json

from .allocation_coverage import csv_text
from .allocation_enrichment import inputs as initial_inputs
from .elementary_audit import report_rows as elementary_rows
from .io import digest, read_csv, record_id

CONFIG = 'config/research_migrations/tx_allocation_review_2026_11_05.json'
INFERRED = 'USER_AUTHORIZED_SAME_PROGRAMME_INFERENCE'
DIRECTIVE = 'USER_CONFIRMED_ELEMENTARY_MODEL'
LITERAL = 'SOURCE_LITERAL_DISTRICT_ENDPOINT'


def inputs(root):
    config = json.loads((root / CONFIG).read_text())
    sources = json.loads((root / config['sources']).read_text())
    decisions = json.loads((root / config['decisions']).read_text())
    resolutions = json.loads((root / config['resolutions']).read_text())
    for path, expected in config['frozen_checkpoint_files'].items():
        if digest(root / path) != expected:
            raise ValueError('Earlier allocation checkpoint changed: ' + path)
    source_keys = {r['key'] for r in sources}
    case_districts = {r['case_id']: r['district_id'] for r in resolutions}
    legacy = {r['allocation_record_id']: r for r in
              read_csv(root / 'data/registry/texas/texas_k_allocation_evidence_pass51.csv')}
    if len(source_keys) != len(sources) or len({d['decision_id'] for d in decisions}) != len(decisions):
        raise ValueError('Duplicate review decision or source key')
    if len(resolutions) != 14 or len({r['case_id'] for r in resolutions}) != 14:
        raise ValueError('The original fourteen review cases must all receive an outcome')
    for decision in decisions:
        if case_districts.get(decision['case_id']) != decision['district_id']:
            raise ValueError('Review decision changed the original case district')
        if any(cid[:6] != decision['district_id'] for cid in decision['donor_campus_ids']):
            raise ValueError('Model donors must be in the same district')
        if decision['compatible_model_labels'] != [decision['model_label']]:
            raise ValueError('Conflicting models cannot supply a unique inherited model')
        if not set(decision['source_keys']) <= source_keys:
            raise ValueError('Review decision lacks a saved source')
        if decision['basis'] not in {'user_directive', 'same_district_type_language_inference', 'literal_district_endpoint'}:
            raise ValueError('Unknown model assignment basis')
        if decision.get('school_year') is not None:
            raise ValueError('Review date cannot become an operating year')
        if decision.get('legacy_donor'):
            donor = decision['legacy_donor']
            original = legacy.get(donor['allocation_record_id'], {})
            if (any(original.get(k) != v for k, v in donor.items())
                    or donor['allocation_label'] != decision['model_label']
                    or donor['TAPR_program_group'] != decision['population_model']):
                raise ValueError('Legacy donor model, programme type or review quality changed')
    return config, sources, decisions, resolutions


def validate_matches(tables, decisions):
    """Reject cross-district, cross-type, cross-language and secondary matches."""
    sites = {r['site_id']: r for r in tables['program_sites']}
    configurations, languages = defaultdict(set), defaultdict(set)
    for row in tables['program_configurations']:
        if row['population_model']:
            configurations[row['site_id']].add(row['population_model'])
    for row in tables['program_languages']:
        if row['language_name'] != 'English':
            languages[row['site_id']].add(row['language_name'])
    elementary, _ = elementary_rows(tables)
    primary = {r['school_id'] for r in elementary if r['audit_scope'] == 'all_recorded_programme_hosts'
               and r['state_code'] == 'TX' and r['elementary_denominator']}
    seen = set()
    for decision in decisions:
        for match in decision['sites']:
            site = sites.get(match['site_id'])
            if not site or site['school_id'] != match['school_id'] or site['program_id'] != match['program_id']:
                raise ValueError('Review assignment invents or changes programme identity')
            if not site['school_id'].startswith('TX-S' + decision['district_id']):
                raise ValueError('Model cannot be inherited across districts')
            if site['school_id'] not in primary:
                raise ValueError('Elementary model cannot be assigned to a secondary-only or unresolved host')
            if configurations[site['site_id']] != {decision['population_model']}:
                raise ValueError('One-way and two-way models cannot be interchanged')
            known = languages[site['site_id']]
            if known and known != {decision['partner_language']}:
                raise ValueError('Model cannot be inherited across instructional languages')
            if not known and match['language_match_basis'] != 'inferred_from_district_Spanish_English_programme_family':
                raise ValueError('An unknown campus language needs an explicit inferred-family basis')
            if match['site_id'] in seen:
                raise ValueError('Multiple reviewed models assigned to one programme')
            seen.add(match['site_id'])


def evidence_status(decision):
    return {'user_directive': DIRECTIVE, 'literal_district_endpoint': LITERAL}.get(decision['basis'], INFERRED)


def schedule_id(decision, match):
    return record_id('schedule', 'TX_USER_MODEL_REVIEW', decision['decision_id'], match['site_id'])


def migrate(builder):
    config, sources, decisions, resolutions = inputs(builder.root)
    for path in [CONFIG, config['sources'], config['decisions'], config['resolutions'], config['retrieval_receipts'],
                 *config['frozen_checkpoint_files']]:
        builder.track_input(path)
    tables = {name: builder.rows(name) for name in builder.tables}
    validate_matches(tables, decisions)
    dataset = builder.dataset(config['dataset_id'], 'TX', 'inventory',
        'Texas user-reviewed allocation classifications', 'repo:' + CONFIG,
        notes='Like programme classifications may be inferred; original donor quality and unresolved distinctions are retained.')
    source_ids = {}
    for source in sources:
        source_ids[source['key']] = builder.source_file(dataset, source['path'], metadata=source.get('metadata_path'))
        if source.get('derived_text_path'):
            builder.track_input(source['derived_text_path'])
    instruction_source = builder.source_file(dataset, CONFIG)
    builder.claim('state', 'TX', 'allocation_model_inference_rule', json.dumps(config['rule'], sort_keys=True),
        instruction_source, 'user_review_rule', status='provisional', method='user_authorized_research_classification',
        notes='User instructions are preserved in the source configuration; assignment dates are not school years.')
    for decision in decisions:
        source = instruction_source if decision['basis'] == 'user_directive' else source_ids[decision['source_keys'][0]]
        for match in decision['sites']:
            sid = schedule_id(decision, match)
            builder.add('allocation_schedules', schedule_id=sid, site_id=match['site_id'], school_id=match['school_id'],
                grade_scope=decision['grade_scope'], reported_model_label=decision['model_label'],
                percentage_basis='Reported programme model classification; English/partner ordering only as stated. ' + decision['limitations'],
                schedule_status='reported_policy_requires_review', evidence_review_status=evidence_status(decision),
                grade_support_status='PUBLISHED_MODEL_ONLY', tested_cohort_exposure='not_established',
                evidence_period_raw=decision['evidence_period_raw'], source_id=source,
                source_locator=decision['case_id'] + '/' + decision['decision_id'],
                notes=decision['limitations'] + ' Language match basis: ' + match['language_match_basis']
                    + ' Source evidence: ' + decision['source_quote'] + ' User instruction source: ' + instruction_source)
            builder.claim('program', match['program_id'], 'reviewed_allocation_model_classification',
                json.dumps(dict(decision=decision, match=match), sort_keys=True), source, sid,
                status='provisional', method=decision['basis'], import_source=instruction_source,
                notes='Inferred classification is not a new campus language observation or observed timetable.')
    # Red Oak already has one-way configurations: affirm the reviewed type without adding a ratio.
    for site in tables['program_sites']:
        if site['school_id'] in {'TX-S070911102', 'TX-S070911107'}:
            builder.claim('program', site['program_id'], 'reviewed_population_model', 'one_way',
                source_ids['tx_policy_070911_1'], 'TX52-R02-RED_OAK', status='documented',
                method='user_review_with_official_programme_description', import_source=instruction_source,
                notes='Overall numerical allocation and kindergarten allocation remain unknown.')
    for resolution in resolutions:
        for cid in resolution['campus_ids']:
            builder.claim('school', 'TX-S' + cid, 'allocation_review_case_resolution',
                json.dumps(resolution, sort_keys=True), instruction_source, resolution['case_id'],
                status='provisional', method='user_review_rule_applied',
                notes='Supersedes the pending decision request for this review round; earlier source claims remain historical evidence.')


def audit_errors(root, tables):
    config, sources, decisions, _ = inputs(root)
    validate_matches(tables, decisions)
    source_rows = {r['source_id']: r for r in tables['sources']}
    additions = [r for r in tables['allocation_schedules']
                 if source_rows[r['source_id']]['dataset_id'] == config['dataset_id']]
    expected = {schedule_id(d, m): (d, m) for d in decisions for m in d['sites']}
    errors = []
    if {r['schedule_id'] for r in additions} != set(expected):
        errors.append('Reviewed programme assignment set changed')
    docs = {s['key']: s for s in sources}
    for row in additions:
        if row['schedule_id'] not in expected:
            continue
        decision, match = expected[row['schedule_id']]
        fingerprint = digest(root / CONFIG) if decision['basis'] == 'user_directive' else docs[decision['source_keys'][0]]['sha256']
        if (row['site_id'] != match['site_id'] or row['school_id'] != match['school_id']
                or row['reported_model_label'] != decision['model_label']
                or row['source_id'] != record_id('source', config['dataset_id'], fingerprint)
                or row['school_year'] is not None or row['grade_scope'] != decision['grade_scope']
                or row['grade_support_status'] != 'PUBLISHED_MODEL_ONLY'
                or row['evidence_review_status'] != evidence_status(decision)
                or row['tested_cohort_exposure'] != 'not_established'):
            errors.append('Review inference scope, provenance or exposure changed: ' + row['schedule_id'])
    ids = set(expected)
    if any(r['schedule_id'] in ids for r in tables['instructional_allocations']):
        errors.append('Model inference acquired unverified named-language time shares')
    return errors


def render_reports(root, tables):
    config, sources, decisions, resolutions = inputs(root)
    errors = audit_errors(root, tables)
    if errors:
        raise ValueError('\n'.join(errors))
    _, _, targets, initial_decisions, _ = initial_inputs(root)
    schools = {r['school_id']: r for r in tables['schools']}
    docs = {r['key']: r for r in sources}
    by_school, by_case = defaultdict(list), defaultdict(list)
    assignments = []
    for decision in decisions:
        for match in decision['sites']:
            by_school[match['school_id']].append(decision)
            by_case[decision['case_id']].append(match)
            assignments.append(dict(case_id=decision['case_id'], decision_id=decision['decision_id'],
                school_id=match['school_id'], school_name=schools[match['school_id']]['school_name'],
                program_id=match['program_id'], site_id=match['site_id'],
                population_model=decision['population_model'], classification_language_pair='English/Spanish',
                language_match_basis=match['language_match_basis'], reported_model_label=decision['model_label'],
                classification_basis=decision['basis'], evidence_review_status=evidence_status(decision),
                grade_scope=decision['grade_scope'], school_year='', evidence_period_raw=decision['evidence_period_raw'],
                donor_campus_ids=' | '.join(decision['donor_campus_ids']),
                legacy_donor_review_status=(decision.get('legacy_donor') or {}).get('pass51_review_status', ''),
                source_urls=' | '.join(docs[k]['url'] for k in decision['source_keys']),
                source_quote_kind=decision['source_quote_kind'], source_quote=decision['source_quote'],
                limitations=decision['limitations']))
    baseline_ids={cid for d in initial_decisions for cid in d['campus_ids']}
    target_ids={r['campus_id'] for r in targets}
    newly_filled={sid[4:] for sid in by_school if sid[4:] in target_ids and sid[4:] not in baseline_ids}
    case_for_campus={cid:r for r in resolutions for cid in r['campus_ids']}
    # Start with the saved prior outcomes so all 598 retain their research receipts.
    import csv
    with (root / 'data/reports/ut_tx_allocation_followup_2026_11_05_texas_598_status.csv').open() as stream:
        prior = list(csv.DictReader(stream))
    target_view=[]
    for row in prior:
        cid=row['campus_id']; dd=by_school.get(row['school_id'], []); rr=case_for_campus.get(cid)
        combined_labels=sorted(set(filter(None,row['model_labels'].split(' | '))) | {d['model_label'] for d in dd})
        updated=dict(row)
        updated.update(baseline_followup_status=row['followup_status'],baseline_model_labels=row['model_labels'],
            followup_status='model_available' if cid in baseline_ids or cid in newly_filled else 'allocation_unknown',
            model_labels=' | '.join(combined_labels),
            source_urls=' | '.join(sorted(set(filter(None,row['source_urls'].split(' | '))) |
                {docs[k]['url'] for d in dd for k in d['source_keys']})))
        target_view.append(dict(**updated,review_round_status=rr['resolution_status'] if rr else 'unchanged',
            review_round_model_labels=' | '.join(sorted({d['model_label'] for d in dd})),
            review_round_classification_bases=' | '.join(sorted({d['basis'] for d in dd})),
            model_status_after_review='model_available' if cid in baseline_ids or cid in newly_filled else 'allocation_unknown',
            review_resolution=rr['resolution'] if rr else ''))
    case_view=[]
    for r in resolutions:
        matches=by_case[r['case_id']]
        case_view.append(dict(case_id=r['case_id'],district=r['district'],campus_count=len(r['campus_ids']),
            resolution_status=r['resolution_status'],assigned_programme_sites=len(matches),
            newly_filled_campuses=len({m['school_id'][4:] for m in matches} & newly_filled),
            resolution=r['resolution'],source_urls=' | '.join(docs[k]['url'] for k in r['source_keys'])))
    summary=dict(review_date=config['date'],review_round=1,original_missing_model_campuses=598,
        prior_followup_model_additions=len(baseline_ids),newly_classified_campuses=len(newly_filled),
        cumulative_model_additions=len(baseline_ids | newly_filled),remaining_without_model=598-len(baseline_ids | newly_filled),
        programme_assignments=len(assignments),campuses_with_programme_assignments=len(by_school),
        assignment_basis_counts=dict(Counter(r['classification_basis'] for r in assignments)),
        interpretation='User-authorized classifications include inferred models. Source/legacy donor quality is retained. Kindergarten time shares, operation dates and cohort exposure are not established.')
    lines=['# Texas review outcomes after the user classification rule','',
        f"The review adds models for {len(newly_filled)} previously unfilled campuses; "
        f"{summary['cumulative_model_additions']} of the original 598 now have model information. "
        f"{summary['remaining_without_model']} remain without a model.",'',
        'Assignments are attached to matching programme strands. A language inferred from a district family is explicitly marked and does not overwrite the language-observation table. '
        'Legacy-donor inferences retain the original NOT_REVIEWED status and unavailable-citation warning. '
        'These classifications do not establish an observed or kindergarten timetable.','']
    for r in case_view:
        lines.extend(['## '+r['case_id']+' — '+r['district'],'',
            '**Outcome:** '+r['resolution_status'],'',r['resolution'],'',
            'Newly filled campuses: '+str(r['newly_filled_campuses'])+'. Programme assignments: '+str(r['assigned_programme_sites'])+'.','',
            'Sources: '+r['source_urls'],''])
    prefix=config['report_prefix']
    return {prefix+'_assignments.csv':csv_text(assignments),prefix+'_case_outcomes.csv':csv_text(case_view),
            prefix+'_598_after_review.csv':csv_text(target_view),prefix+'_summary.json':json.dumps(summary,indent=2)+'\n',
            prefix+'_outcomes.md':'\n'.join(lines)}
