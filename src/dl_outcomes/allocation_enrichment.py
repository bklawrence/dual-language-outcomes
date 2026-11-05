"""User-authorized Utah model and source-reviewed Texas allocation additions."""
from collections import Counter, defaultdict
import json

from .io import digest, read_csv, record_id
from .allocation_coverage import csv_text
from .elementary_audit import report_rows as elementary_rows

CONFIG='config/research_migrations/ut_tx_allocations_2026_11_05.json'
REPORT='data/reports/ut_tx_allocation_followup_2026_11_05'


def inputs(root):
    config=json.loads((root/CONFIG).read_text())
    sources=json.loads((root/config['sources']).read_text())
    targets=read_csv(root/config['texas_targets'])
    if digest(root/config['texas_targets'])!=config['texas_targets_sha256']:
        raise ValueError('Fixed Texas target cohort changed')
    decisions=json.loads((root/config['texas_decisions']).read_text())
    reviews=json.loads((root/config['texas_reviews']).read_text())
    validate_decisions(targets, decisions, sources, reviews)
    for source in sources:
        if source.get('derived_text_path') and digest(root/source['derived_text_path'])!=source['derived_text_sha256']:
            raise ValueError('Changed derived publication text: '+source['key'])
    old_roster=root/'data/raw/western_plains_2026_11_04/wp_ut_roster26.pdf'
    new_roster=root/next(s['path'] for s in sources if s['key']==config['utah_rule']['roster_source'])
    if digest(old_roster)!=digest(new_roster):
        raise ValueError('Utah roster changed: re-extract and reconcile before reporting an exact match')
    return config,sources,targets,decisions,reviews


def validate_decisions(targets, decisions, sources, reviews):
    """Keep additions inside the fixed research cohort and their reviewed scope."""
    target_ids={r['campus_id'] for r in targets}
    if len(targets)!=598 or len(target_ids)!=598:
        raise ValueError('Texas follow-up lost its fixed 598-campus starting universe')
    keys={r['key'] for r in sources}
    if len(keys)!=len(sources):
        raise ValueError('Duplicate follow-up source key')
    for rows,identity in [(decisions,'decision_id'),(reviews,'case_id')]:
        if len({r[identity] for r in rows})!=len(rows):
            raise ValueError('Duplicate allocation decision or review case')
        for row in rows:
            campuses=row['campus_ids']
            if not campuses or len(set(campuses))!=len(campuses) or not set(campuses)<=target_ids:
                raise ValueError('Texas decision escaped the missing-model target universe')
            if any(cid[:6]!=row['district_id'] for cid in campuses):
                raise ValueError('District policy assigned across LEA boundaries')
            if not row['source_quote'] or not row['source_keys'] or not set(row['source_keys'])<=keys:
                raise ValueError('Allocation lacks reviewed source evidence')
    from .elementary_audit import numeric_model
    for row in decisions:
        if row['status']!='accepted':
            raise ValueError('Unaccepted numerical decision belongs in the review queue')
        if row['evidence_scope'] not in {'district_policy_only','campus_documented'}:
            raise ValueError('Unknown allocation evidence scope')
        if not numeric_model(row['model_label']):
            raise ValueError('Accepted model is not a quantified instructional allocation')


def migrate(b):
    config,sources,targets,decisions,reviews=inputs(b.root)
    for path in [CONFIG,config['sources'],config['texas_targets'],config['texas_decisions'],config['texas_reviews'],config['texas_research_log']]:
        b.track_input(path)
    datasets={state:b.dataset(state+'_ALLOCATION_FOLLOWUP_2026_11_05',state,'inventory',
        state+' elementary allocation follow-up','repo:'+config['sources'],
        notes='Additive model evidence; previous programme identities, source periods and assessment outputs preserved.') for state in ['UT','TX']}
    source_ids={}
    for doc in sources:
        source_ids[doc['key']]=b.source_file(datasets[doc['state']],doc['path'],metadata=doc['metadata_path'])
        if doc.get('derived_text_path'):
            b.track_input(doc['derived_text_path'])
    rule=config['utah_rule']
    rule_source=b.source_file(datasets['UT'],CONFIG)
    b.claim('state','UT','elementary_DLI_default_model',json.dumps(rule,sort_keys=True),rule_source,
        'utah_rule',status='provisional',method='user_authorized_statewide_model_assignment',
        notes='User accepted a statewide elementary 50/50 model; campus-year exposure is not inferred.')
    tables={name:b.rows(name) for name in b.tables}
    elementary,_=elementary_rows(tables)
    utah={r['school_id'] for r in elementary if r['state_code']=='UT' and r['audit_scope']=='all_recorded_programme_hosts' and r['elementary_denominator']}
    for sid in sorted(utah):
        source=source_ids[rule['corroborating_source']]
        schedule=record_id('schedule','UT_statewide_elementary_50_50',sid)
        b.add('allocation_schedules',schedule_id=schedule,school_id=sid,
            grade_scope=rule['grade_scope'],reported_model_label=rule['model'],
            percentage_basis='Statewide elementary DLI model: half English and half target-language instruction; grade/track timetable not independently observed',
            schedule_status='reported_policy_requires_review',evidence_review_status='USER_AUTHORIZED_STATEWIDE_ELEMENTARY_MODEL',
            grade_support_status='PUBLISHED_MODEL_ONLY',tested_cohort_exposure='not_established',
            evidence_period_raw='Statewide policy assignment accepted 2026-11-05; source/model applicability is not a campus operating year',
            source_id=source,source_locator=rule['source_quote']+'; school='+sid,
            notes=rule['limitations']+' Language tracks remain separate. Assignment record: '+rule_source)
        b.claim('school',sid,'assigned_elementary_allocation_model',rule['model'],source,
            schedule,status='provisional',method='user_authorized_statewide_model_assignment',import_source=rule_source,
            notes=rule['limitations'])
    target_ids={r['campus_id'] for r in targets}
    used=set()
    for decision in decisions:
        if decision['decision_id'] in used:raise ValueError('Duplicate allocation decision')
        used.add(decision['decision_id'])
        if not set(decision['campus_ids'])<=target_ids:raise ValueError('Texas decision escaped the missing-model target universe')
        if decision['status']!='accepted':continue
        if not decision['source_quote'] or not decision['source_keys']:raise ValueError('Allocation lacks reviewed source evidence')
        for cid in decision['campus_ids']:
            sid='TX-S'+cid
            if (sid,) not in b.tables['schools']:raise ValueError('Allocation invents a campus')
            if cid[:6]!=decision['district_id']:raise ValueError('District policy assigned across LEA boundaries')
            source=source_ids[decision['source_keys'][0]]
            schedule=record_id('schedule','TX_allocation_followup',decision['decision_id'],cid)
            b.add('allocation_schedules',schedule_id=schedule,school_id=sid,
                school_year=decision.get('school_year'),grade_scope=decision['grade_scope'],
                reported_model_label=decision['model_label'],percentage_basis=decision['percentage_basis'],
                schedule_status='reported_policy_requires_review',evidence_review_status=decision['evidence_scope'],
                grade_support_status=decision.get('grade_support_status') or
                    ('CAMPUS_GRADE_BAND_MODEL' if decision['evidence_scope']=='campus_documented' else 'DISTRICT_GRADE_BAND_MODEL'),
                evidence_period_raw=decision['evidence_period_raw'],tested_cohort_exposure='not_established',
                source_id=source,source_locator=decision['source_locator'],
                notes=decision['rationale']+' Quote: '+decision['source_quote']+' Campus/year or reporting-category delivery is not inferred from a district policy.')
            b.claim('school',sid,'allocation_followup_model',json.dumps(decision,sort_keys=True),source,
                decision['decision_id'],year=decision.get('school_year'),period=decision['evidence_period_raw'],
                status='documented' if decision['evidence_scope']=='campus_documented' else 'district_policy_only',
                notes='Model information at its stated evidence scope; no instructional-language pair or cohort allocation invented.')
    for review in reviews:
        for cid in review['campus_ids']:
            b.claim('school','TX-S'+cid,'allocation_followup_pending_review',
                json.dumps(review,sort_keys=True),source_ids[review['source_keys'][0]],review['case_id'],
                status='unverified',method='source_scope_review_pending',
                notes='Source detail retained without assigning a total instructional-time model.')


def audit_errors(root,tables):
    """Verify that reviewed additions never become track timetables or exposure."""
    config,sources,targets,decisions,reviews=inputs(root)
    errors=[]
    source_by_id={r['source_id']:r for r in tables['sources']}
    docs={r['key']:r for r in sources}
    new=[r for r in tables['allocation_schedules'] if source_by_id[r['source_id']]['dataset_id']
         in {'UT_ALLOCATION_FOLLOWUP_2026_11_05','TX_ALLOCATION_FOLLOWUP_2026_11_05'}]
    primary,_=elementary_rows(tables)
    utah={r['school_id'] for r in primary if r['state_code']=='UT' and
          r['audit_scope']=='all_recorded_programme_hosts' and r['elementary_denominator']}
    expected_utah={record_id('schedule','UT_statewide_elementary_50_50',sid):sid for sid in utah}
    expected_texas={record_id('schedule','TX_allocation_followup',d['decision_id'],cid):(cid,d)
                    for d in decisions for cid in d['campus_ids']}
    if {r['schedule_id'] for r in new}!=set(expected_utah)|set(expected_texas):
        errors.append('Follow-up schedule set differs from the reviewed elementary assignments')
    for row in new:
        if row['site_id'] or row['tested_cohort_exposure']!='not_established':
            errors.append('Follow-up policy became a track timetable or cohort exposure: '+row['schedule_id'])
        if row['schedule_id'] in expected_utah:
            if (row['school_id']!=expected_utah[row['schedule_id']] or row['reported_model_label']!='50/50'
                    or row['school_year'] is not None or row['grade_support_status']!='PUBLISHED_MODEL_ONLY'
                    or row['source_id']!=record_id('source','UT_ALLOCATION_FOLLOWUP_2026_11_05',
                        docs[config['utah_rule']['corroborating_source']]['sha256'])
                    or row['evidence_review_status']!='USER_AUTHORIZED_STATEWIDE_ELEMENTARY_MODEL'):
                errors.append('Utah policy assignment scope changed: '+row['schedule_id'])
        elif row['schedule_id'] in expected_texas:
            cid,decision=expected_texas[row['schedule_id']]
            if (row['school_id']!='TX-S'+cid or row['school_year']!=decision.get('school_year')
                    or row['reported_model_label']!=decision['model_label']
                    or row['grade_scope']!=decision['grade_scope']
                    or row['evidence_period_raw']!=decision['evidence_period_raw']
                    or row['source_id']!=record_id('source','TX_ALLOCATION_FOLLOWUP_2026_11_05',
                        docs[decision['source_keys'][0]]['sha256'])
                    or row['evidence_review_status']!=decision['evidence_scope']):
                errors.append('Texas reviewed model or source period changed: '+row['schedule_id'])
    new_ids={r['schedule_id'] for r in new}
    if any(r['schedule_id'] in new_ids for r in tables['instructional_allocations']):
        errors.append('Follow-up model labels acquired unreviewed named-language shares')
    return errors


def render_reports(root,tables):
    config,sources,targets,decisions,reviews=inputs(root)
    errors=audit_errors(root,tables)
    if errors:raise ValueError('\n'.join(errors))
    docs={r['key']:r for r in sources}
    elementary,summary=elementary_rows(tables)
    utah=[r for r in elementary if r['state_code']=='UT' and r['audit_scope']=='all_recorded_programme_hosts' and r['elementary_denominator']]
    utah_view=[dict(school_id=r['school_id'],school_name=r['school_name'],model='50/50',
        model_basis=config['utah_rule']['basis'],instruction_languages_attribution='English/target model; individual language evidence retained separately',
        programme_ids=r['programme_ids'],source_url=docs[config['utah_rule']['corroborating_source']]['url'],
        notes=config['utah_rule']['limitations']) for r in utah]
    programmes=json.loads((root/'data/registry/western_plains_2026_11_04/ut_programmes.json').read_text())
    raw_rows=json.loads((root/'data/registry/western_plains_2026_11_04/extractions/ut_roster_rows.json').read_text())
    links=defaultdict(list)
    for p in programmes:
        for observation in p['observations']:
            if observation['source']=='wp_ut_roster26':
                raw=observation['raw']
                for language in observation['languages']:
                    links[(raw['district'],raw['school'],raw['page'],raw['block'],language)].append(p['program_id'])
    reconciliation=[]
    for row in raw_rows:
        for language in row['language'].split(', '):
            matches=links[(row['district'],row['school'],row['page'],row['block'],language)]
            if len(matches)!=1:raise ValueError('UT roster cell does not map to exactly one retained research group')
            reconciliation.append(dict(roster_school_year='2026-27',district=row['district'],school=row['school'],
                language=language,pdf_page=row['page'],pdf_text_block=row['block'],program_id=matches[0],
                status='matched_existing_record',source_url=docs[config['utah_rule']['roster_source']]['url']))
    accepted=defaultdict(list);pending=defaultdict(list)
    target_by_id={r['campus_id']:r for r in targets}
    added_view=[]
    for d in decisions:
        if d['status']=='accepted':
            for cid in d['campus_ids']:
                accepted[cid].append(d)
                added_view.append(dict(decision_id=d['decision_id'],campus_id=cid,
                    school_id=target_by_id[cid]['school_id'],school_name=target_by_id[cid]['school_name'],
                    district=d['district'],reported_model_label=d['model_label'],grade_scope=d['grade_scope'],
                    evidence_scope=d['evidence_scope'],school_year=d.get('school_year'),
                    evidence_period_raw=d['evidence_period_raw'],percentage_basis=d['percentage_basis'],
                    source_urls=' | '.join(docs[k]['url'] for k in d['source_keys']),
                    archived_source_paths=' | '.join(docs[k]['path'] for k in d['source_keys']),
                    source_quote_kind=d.get('source_quote_kind','source_excerpt'),
                    source_quote=d['source_quote'],notes=d['rationale']))
    for r in reviews:
        for cid in r['campus_ids']:pending[cid].append(r)
    log=json.loads((root/config['texas_research_log']).read_text())
    by_district={r['district_id']:r for r in log}
    target_view=[]
    for row in targets:
        cid=row['campus_id'];dd=accepted.get(cid,[]);rr=pending.get(cid,[]);research=by_district.get(row['district_id'],{})
        status=('model_added_with_review_pending' if rr else 'model_added') if dd else 'pending_user_review' if rr else research.get('outcome','not_yet_researched')
        if not dd and not rr and status.startswith('models_added'):
            status='model_found_campus_scope_unresolved'
        target_view.append(dict(**row,followup_status=status,model_labels=' | '.join(sorted({d['model_label'] for d in dd})),
            decision_ids=' | '.join(sorted(d['decision_id'] for d in dd)),review_case_ids=' | '.join(sorted(r['case_id'] for r in rr)),
            source_urls=' | '.join(sorted({docs[k]['url'] for d in dd+rr for k in d['source_keys']})),
            checked_source_urls=' | '.join(r['url'] for r in research.get('checked_sources',[])),
            research_notes=research.get('notes','')))
    review_view=[]
    review_text=['# Texas allocation questions for review','',
        'These cases preserve source evidence while withholding the disputed allocation. '
        'A campus can have a clear model label and a separate unresolved question, as in Midlothian. '
        'Choices are review options, not approval to infer missing percentages.','']
    for row in reviews:
        urls=[docs[k]['url'] for k in row['source_keys']]
        review_view.append(dict(case_id=row['case_id'],district=row['district'],campus_count=len(row['campus_ids']),
            campus_ids=' | '.join(row['campus_ids']),campus_names=' | '.join(row['campus_names']),
            issue=row['issue'],source_urls=' | '.join(urls),source_quote=row['source_quote'],
            question=row['question'],choices=' | '.join(row['choices']),status=row['status']))
        review_text.extend(['## '+row['case_id']+' — '+row['district'],'',
            '**Campuses ('+str(len(row['campus_ids']))+'):** '+', '.join(row['campus_names']),
            '',row['issue'],'','Source: '+'; '.join(urls),'',
            '> '+row['source_quote'],'',row['question'],'',
            *['- '+choice for choice in row['choices']],''])
    filled=set(accepted)
    pending_ids=set(pending)-filled
    counts=dict(starting_texas_campuses=598,districts=len({r['district_id'] for r in targets}),
        campuses_with_model_added=len(filled),remaining_without_model=598-len(filled),
        unfilled_campuses_pending_user_review=len(pending_ids),review_cases=len(reviews),
        campuses_with_model_and_separate_review=len(set(pending)&filled),
        district_research_receipts=len(log),
        unfilled_status_counts=dict(Counter(r['followup_status'] for r in target_view if not r['decision_ids'])),
        utah_elementary_policy_assignments=len(utah_view),utah_roster_language_cells=len(reconciliation),
        utah_roster_school_rows=len(raw_rows),utah_roster_source_year='2026-27',
        utah_roster_reconciliation_basis='Fresh PDF is byte-identical to the already extracted official roster; all cells map to retained programme groups.',
        interpretation='Model availability across source periods; no campus-year operating confirmation, track-specific timetable, language pair or tested-cohort exposure inferred.')
    return {REPORT+'_utah_models.csv':csv_text(utah_view),REPORT+'_utah_roster_reconciliation.csv':csv_text(reconciliation),
            REPORT+'_texas_598_status.csv':csv_text(target_view),
            REPORT+'_texas_added_models.csv':csv_text(added_view),
            REPORT+'_texas_review.csv':csv_text(review_view),REPORT+'_texas_review.md':'\n'.join(review_text),
            REPORT+'_summary.json':json.dumps(counts,indent=2,ensure_ascii=False)+'\n'}
