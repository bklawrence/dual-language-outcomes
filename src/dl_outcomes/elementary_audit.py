"""Audit numerical allocation-model completeness for schools serving grades K–5.

Preserves the separate, stricter K-schedule report. Source model availability is
not a claim about exact grade timetables, every strand or participant exposure.
"""
from collections import defaultdict
import json
import re
import unicodedata

from .allocation_coverage import csv_text, report_rows as k_report, select_grade_rows, reference_year

CONFIG = 'config/research_migrations/elementary_allocation_audit_2026_11_04.json'
PREFIX = 'data/reports/elementary_allocation_coverage_2026_11_04'


def normalize(value, *, district=False):
    text = unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().casefold()
    text = re.sub(r'[^a-z0-9]+',' ',text).strip()
    words = {'elem':'elementary','el':'elementary','es':'elementary','sch':'school',
             'sd':'school district','usd':'unified school district','isd':'independent school district',
             'cusd':'community unit school district','ccsd':'community consolidated school district',
             'cisd':'consolidated independent school district','jr':'junior','sr':'senior','dist':'district'}
    text = ' '.join(words.get(w,w) for w in text.split())
    if district:
        return ' '.join(w for w in text.split() if w not in {'school','schools','district','public','no','number'})
    return re.sub(r'\s+school$','',text).replace('h s','high').replace('m s','middle')


def native_key(state, native):
    if state=='WA':
        return native.split('-')[-1].zfill(4)
    if state=='TX':
        return native.split('-')[-1]
    return re.sub(r'\D','',native)


def directory_rows(root):
    config = json.loads((root/CONFIG).read_text())
    rows = []
    for path in sorted((root/config['raw_directory']).glob('ccd_20*.json')):
        if '.metadata.' in path.name:
            continue
        source = path.relative_to(root).as_posix()
        rows.extend(dict(r,snapshot_path=source) for r in json.loads(path.read_text())['results'])
    return rows


def grade_matches(tables, rows, aliases=()):
    """Accept existing native IDs or unique exact normalized school+district names."""
    schools = {r['school_id']:r for r in tables['schools']}
    hosts = {r['school_id'] for r in tables['program_sites']}
    codes = {int(r['state_fips']):r['state_code'] for r in tables['states']}
    by_nces, by_native, by_name = {}, defaultdict(list), defaultdict(list)
    for row in rows:
        state = codes[row['fips']]
        old = by_nces.get(row['ncessch'])
        if old is None or (elementary_span(row['lowest_grade_offered'],row['highest_grade_offered'])!='unknown',row['year']) > (elementary_span(old['lowest_grade_offered'],old['highest_grade_offered'])!='unknown',old['year']):
            by_nces[row['ncessch']] = row
        by_native[(state,native_key(state,row['seasch']))].append(row)
        by_name[(state,normalize(row['school_name']),normalize(row['lea_name'],district=True))].append(row)
    identifiers = defaultdict(set)
    for row in tables['identifiers']:
        if row['entity_type']=='school':
            identifiers[row['entity_id']].add((row['namespace'],row['native_id']))
    sites_by_program = defaultdict(set)
    for row in tables['program_sites']:
        sites_by_program[row['program_id']].add(row['school_id'])
    for claim in tables['evidence_claims']:
        if claim['attribute']=='reviewed_inventory_snapshot':
            record = json.loads(claim['reported_value'])
            if record['school_id']:
                for sid in sites_by_program[claim['entity_id']]:
                    identifiers[sid].add((record['school_id_namespace'],record['school_id']))
    districts = {r['district_id']:r['district_name'] for r in tables['districts']}
    memberships = defaultdict(set)
    for row in tables['school_district_history']:
        memberships[row['school_id']].add(normalize(districts[row['district_id']],district=True))
    reviewed = {r['school_id']:r for r in aliases}
    for key,values in by_native.items():
        by_native[key] = list({r['ncessch']:by_nces[r['ncessch']] for r in values}.values())
    matches = {}
    for sid in sorted(hosts):
        state, name = schools[sid]['state_code'], normalize(schools[sid]['school_name'])
        candidates = {}
        for namespace, native in identifiers[sid]:
            if namespace=='NCES_school_id' and native in by_nces:
                candidates[native] = ('existing_nces_id',by_nces[native])
            elif namespace in {'TX_TEA_campus_id','WA_OSPI_school_code','CA_CDS','IL_state_school_id'}:
                for row in by_native[(state,native_key(state,native))]:
                    candidates[row['ncessch']] = ('exact_state_school_id',row)
        if len(candidates)==1:
            if sid in reviewed and reviewed[sid]['ncessch'] not in candidates:
                raise ValueError('Reviewed grade alias contradicts an existing native ID: '+sid)
            method, row = next(iter(candidates.values()))
        elif sid in reviewed:
            decision = reviewed[sid]
            row = by_nces[decision['ncessch']]
            if codes[row['fips']]!=state or not decision['rationale']:
                raise ValueError('Invalid reviewed grade-context alias: '+sid)
            method = 'reviewed_grade_context_alias'
        else:
            candidates = {r['ncessch']:r for district in memberships[sid]
                          for r in by_name[(state,name,district)]}
            if len(candidates)!=1:
                continue
            row, method = next(iter(candidates.values())), 'exact_normalized_school_and_district'
        matches[sid] = dict(row,match_method=method)
    return matches


def prepare_grade_context(b):
    """Track archived context in portable builds without adding schools/programmes."""
    config = json.loads(b.track_input(CONFIG).read_text())
    dataset = b.dataset('CCD_ELEMENTARY_GRADE_AUDIT',None, 'inventory',
        'School-grade context for the elementary allocation audit',
        'https://educationdata.urban.org/api/v1/schools/ccd/directory/2024/',
        publisher='NCES CCD via Urban Institute; cited school/district grade statements',
        notes='CCD acquisition limited to directory IDs, names and grades; named school profiles supply grade exceptions. No new assessment or demographic measures imported. Matches are grade context, not DL confirmation or durable identity reconciliation.')
    source_ids = {}
    for metadata in sorted((b.root/config['raw_directory']).glob('*.metadata.json')):
        meta = json.loads(metadata.read_text())
        path = b.root/meta['snapshot_path'] if meta.get('snapshot_path') else metadata.with_name(metadata.name.replace('.metadata.json','.json'))
        source = b.source_file(dataset,path,metadata=metadata)
        b.tables['sources'][(source,)]['evidence_period_raw'] = ('2023-24' if path.name.startswith('ccd_2023') else '2024-25') if path.name.startswith('ccd_') else meta.get('evidence_period_raw','variable definitions')
        source_ids[path.relative_to(b.root).as_posix()] = source
    rows = directory_rows(b.root)
    if not rows or len({(r['ncessch'],r['year']) for r in rows})!=len(rows):
        raise ValueError('Missing/duplicate grade-directory records')
    tables = {name:b.rows(name) for name in b.tables}
    matches = grade_matches(tables,rows,config['school_aliases'])
    for sid,row in matches.items():
        b.claim('school',sid,'elementary_audit_school_grade_context',json.dumps(row,sort_keys=True),
            source_ids[row['snapshot_path']],'ncessch='+row['ncessch'],year=str(row['year'])+'-'+str((row['year']+1)%100).zfill(2),
            status='documented',notes='Dated school-grade context only. Match method: '+row['match_method']+'. No new official identity crosswalk or DL programme confirmation inferred.')
    for decision in config.get('manual_school_grades',[]):
        sid = decision['school_id']
        if (sid,) not in b.tables['schools'] or sid in matches:
            raise ValueError('Manual grade context duplicates a match or invents a school: '+sid)
        row = dict(ncessch=None,lowest_grade_offered=decision['low'],highest_grade_offered=decision['high'],
                   snapshot_path=decision['snapshot_path'],match_method='official_named_school_grade_statement')
        b.claim('school',sid,'elementary_audit_school_grade_context',json.dumps(row,sort_keys=True),
            source_ids[decision['snapshot_path']],decision['locator'],period=decision['evidence_period_raw'],
            status='documented',notes=decision['excerpt']+' This is school-grade context, not DL-programme grade/allocation confirmation.')


def elementary_span(low, high):
    """CCD -1 means pre-K; missing/ungraded codes never become grade ranges."""
    if low is None or high is None or low < -1 or high < -1 or low > 13 or high > 13 or low > high:
        return 'unknown'
    if high==-1:
        return 'preschool_only'
    return 'elementary' if low<=5 else 'secondary_6_plus'


def elementary_scope(scope):
    text = (scope or '').casefold().replace('–','-').replace('—','-').strip()
    if not text or text in {'not_reported','unknown'}:
        return 'unknown'
    if 'unresolved' in text or 'campus-specific grades unverified' in text:
        return 'unknown'
    if '|' in text:
        values = {elementary_scope(s) for s in text.split('|')}
        return 'elementary' if 'elementary' in values else 'unknown' if 'unknown' in values else next(iter(values))
    if re.search(r'\bgrades?\s+(\d+)(?:\s*-\s*\d+)?',text):
        match = re.search(r'\bgrades?\s+(\d+)(?:\s*-\s*(\d+))?',text)
        return elementary_span(int(match[1]),int(match[2] or match[1]))
    if 'elementary' in text or re.search(r'\bk(?:indergarten|g)?\b',text):
        return 'preschool_only' if text in {'pre-k','pre k'} else 'elementary'
    if any(s in text for s in ['secondary','middle','high school']):
        return 'secondary_6_plus'
    match = re.search(r'(?:^|grades? )(tk|pre-?k|pk|ece|\d+)(?:st|nd|rd|th)?(?:\s*-\s*(\d+)(?:st|nd|rd|th)?)?',text)
    if match:
        low = -1 if not match[1].isdigit() else int(match[1])
        high = int(match[2]) if match[2] else low
        return elementary_span(low,high)
    return 'unknown'


def numeric_model(label):
    """Require an actual allocation combination totaling 100; no pupil ratios."""
    text = str(label or '').replace('–','-').replace('—','-')
    if any(w in text.casefold() for w in ['student','pupil mix','speakers','enrollment','demographic']):
        return False
    for match in re.finditer(r'(?<![\d.])\d{1,3}(?:\.\d+)?(?:\s*[/:-]\s*\d{1,3}(?:\.\d+)?){1,3}(?![\d.])',text):
        values = [float(x) for x in re.findall(r'\d+(?:\.\d+)?',match[0])]
        for start in range(len(values)-1):
            for end in range(start+2,len(values)+1):
                combo = values[start:end]
                if all(0<=x<=100 for x in combo) and abs(sum(combo)-100)<0.01:
                    return True
    percents = [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)\s*%',text)]
    return 100 in percents or (len(percents)>=2 and all(0<=x<=100 for x in percents) and abs(sum(percents)-100)<0.01)


def report_rows(tables):
    k_details,_,_ = k_report(tables)
    current_sites = {r['site_id'] for r in k_details if r['in_reference_working_set']}
    k_by_school = defaultdict(list)
    for row in k_details:k_by_school[row['school_id']].append(row)
    schools = {r['school_id']:r for r in tables['schools']}
    programs = {r['program_id']:r for r in tables['programs']}
    configs, sites_by_school, schedules = [defaultdict(list) for _ in range(3)]
    contexts = {}
    plans = defaultdict(list)
    for row in tables['instructional_allocations']:plans[row['schedule_id']].append(row)
    for row in tables['program_configurations']:configs[row['site_id']].append(row)
    for row in tables['program_sites']:sites_by_school[row['school_id']].append(row)
    for row in tables['allocation_schedules']:schedules[row['school_id']].append(row)
    for row in tables['evidence_claims']:
        if row['attribute']=='elementary_audit_school_grade_context':
            contexts[row['entity_id']] = (row,json.loads(row['reported_value']))
    details = []
    for sid, sites in sorted(sites_by_school.items()):
        school = schools[sid];state = school['state_code']
        selected_grades = [r for site in sites for r in select_grade_rows(configs[site['site_id']],state)]
        context = contexts.get(sid)
        source_ids, grade_ids = set(), set()
        if context:
            claim,row = context
            eligibility = elementary_span(row['lowest_grade_offered'],row['highest_grade_offered'])
            grade_basis, native = row['match_method'],row['ncessch']
            low,high = row['lowest_grade_offered'],row['highest_grade_offered']
            grade_ids.add(claim['claim_id']);source_ids.add(claim['source_id'])
        else:
            eligibility,grade_basis,native,low,high = 'unknown','not_established',None,None,None
        if eligibility=='unknown':
            documented_k = [r for r in k_by_school[sid] if r['k_eligibility']=='eligible_k']
            if documented_k:
                eligibility,grade_basis='elementary','documented_programme_k_scope_proxy_for_school'
                grade_ids.update(x for r in documented_k for x in r['grade_evidence_record_ids'].split(' | ') if x)
        if eligibility=='unknown':
            scopes = {elementary_scope(r['grade_scope']) for r in selected_grades}
            if any(not select_grade_rows(configs[site['site_id']],state) for site in sites):scopes.add('unknown')
            if 'elementary' in scopes:eligibility='elementary'
            elif scopes and 'unknown' not in scopes:
                eligibility='secondary_6_plus' if 'secondary_6_plus' in scopes else 'preschool_only'
            if eligibility!='unknown':
                grade_basis='reported_programme_scope_proxy_for_school'
                grade_ids.update(r['configuration_id'] for r in selected_grades)
                source_ids.update(r['source_id'] for r in selected_grades)
        in_working = any(r['site_id'] in current_sites for r in sites)
        for scope in ['reference_working_set','all_recorded_programme_hosts']:
            eligible_sites = [r for r in sites if r['site_id'] in current_sites] if scope=='reference_working_set' else sites
            if not eligible_sites:continue
            site_ids = {r['site_id'] for r in eligible_sites}
            evidence = []
            for site in eligible_sites:
                for row in configs[site['site_id']]:
                    year=reference_year(state)
                    if state=='WA' and row['school_year']!='2025-26':continue
                    if scope=='reference_working_set' and year and row['school_year'] and row['school_year']>year:continue
                    if numeric_model(row['reported_model_label']) and elementary_scope(row['grade_scope']) not in {'secondary_6_plus','preschool_only'}:
                        evidence.append(dict(record_id=row['configuration_id'],source_id=row['source_id'],
                            label=row['reported_model_label'],grade=row['grade_scope'],period=row['evidence_period_raw'],flag='published_model_label'))
            for row in schedules[sid]:
                if row['site_id'] and row['site_id'] not in site_ids:continue
                year=reference_year(state)
                if scope=='reference_working_set' and year and row['school_year'] and row['school_year']>year:continue
                if row['grade_support_status'] in {'SOURCE_DOES_NOT_SUPPORT_PROGRAM_GRADE_PERIOD','UNRECOVERED','EARLIER_GRADE_PROXY_NOT_TARGET_QUANTIFIED'}:continue
                if not (numeric_model(row['reported_model_label']) or plans[row['schedule_id']]) or elementary_scope(row['grade_scope']) in {'secondary_6_plus','preschool_only'}:continue
                label = row['reported_model_label']
                if plans[row['schedule_id']] and not numeric_model(label):
                    label += ' ['+'; '.join(r['language_name']+' '+str(r['instruction_share_pct'])+'%' for r in plans[row['schedule_id']])+']'
                evidence.append(dict(record_id=row['schedule_id'],source_id=row['source_id'],label=label,
                    grade=row['grade_scope'],period=row['evidence_period_raw'],flag=row['grade_support_status'] or 'not_reported'))
            counted = eligibility=='elementary' and bool(evidence)
            details.append(dict(audit_scope=scope,state_code=state,reference_working_set_year=reference_year(state),
                school_id=sid,school_name=school['school_name'],nces_grade_context_id=native,
                school_grade_low=low,school_grade_high=high,school_grade_reference_year=claim['valid_from_year'] if context else None,
                school_grade_evidence_period=claim['evidence_period_raw'] if context else None,
                elementary_classification=eligibility,grade_classification_basis=grade_basis,
                programme_grade_scopes=' | '.join(sorted({r['grade_scope'] for r in selected_grades})),
                grade_evidence_ids=' | '.join(sorted(grade_ids)),grade_source_ids=' | '.join(sorted(source_ids)),
                elementary_denominator=int(eligibility=='elementary'),has_numerical_allocation_model=int(counted),
                allocation_status='model_available' if counted else 'allocation_missing' if eligibility=='elementary' else 'not_applicable_secondary' if eligibility=='secondary_6_plus' else 'grade_scope_needs_review' if eligibility=='unknown' else 'preschool_only_excluded',
                numerical_model_labels=' | '.join(sorted({r['label'] for r in evidence})),
                model_evidence_ids=' | '.join(sorted({r['record_id'] for r in evidence})),
                model_source_ids=' | '.join(sorted({r['source_id'] for r in evidence})),
                model_source_periods=' | '.join(sorted({r['period'] or 'not_reported' for r in evidence})),
                model_review_flags=' | '.join(sorted({r['flag'] for r in evidence})),
                programme_ids=' | '.join(sorted({r['program_id'] for r in eligible_sites})),
                reference_working_set_member=int(in_working)))
    # Deduplicate research aliases within this audit without rewriting the
    # canonical registry or asserting a durable historical identity crosswalk.
    units=defaultdict(list)
    for row in details:
        unit='NCES-'+row['nces_grade_context_id'] if row['nces_grade_context_id'] else row['school_id']
        units[(row['audit_scope'],row['state_code'],unit)].append(row)
    deduplicated=[]
    join_fields=['grade_evidence_ids','grade_source_ids','programme_grade_scopes','numerical_model_labels',
                 'model_evidence_ids','model_source_ids','model_source_periods','model_review_flags','programme_ids']
    for (_,_,unit),rows in sorted(units.items()):
        if len({r['elementary_classification'] for r in rows})!=1:
            raise ValueError('Audit aliases have conflicting grade classifications: '+unit)
        row=dict(rows[0],audit_school_id=unit,research_school_ids=' | '.join(sorted(r['school_id'] for r in rows)))
        for field in join_fields:
            row[field]=' | '.join(sorted({x for r in rows for x in r[field].split(' | ') if x}))
        row['has_numerical_allocation_model']=max(r['has_numerical_allocation_model'] for r in rows)
        row['reference_working_set_member']=max(r['reference_working_set_member'] for r in rows)
        deduplicated.append(row)
    details=deduplicated
    summary=[]
    for scope in ['reference_working_set','all_recorded_programme_hosts']:
        for state in sorted({r['state_code'] for r in details}):
            rows=[r for r in details if r['audit_scope']==scope and r['state_code']==state]
            elementary=[r for r in rows if r['elementary_denominator']]
            numerator=sum(r['has_numerical_allocation_model'] for r in elementary)
            unknown=sum(r['elementary_classification']=='unknown' for r in rows)
            summary.append(dict(audit_scope=scope,state_code=state,reference_working_set_year=reference_year(state),
                inventory_school_units=len(rows),elementary_school_units=len(elementary),
                elementary_schools_with_numerical_model=numerator,
                numerical_allocation_coverage_pct=round(100*numerator/len(elementary),1) if elementary else None,
                elementary_schools_missing_numerical_model=len(elementary)-numerator,
                secondary_6_plus_school_units_excluded=sum(r['elementary_classification']=='secondary_6_plus' for r in rows),
                preschool_only_school_units_excluded=sum(r['elementary_classification']=='preschool_only' for r in rows),
                unresolved_grade_school_units=unknown,
                programme_grade_proxy_school_units=sum(r['grade_classification_basis'].endswith('_proxy_for_school') for r in elementary),
                schools_with_flagged_model_evidence=sum(bool({'MODEL_LABEL_MINUTES_DIFFER','CONFLICTING_SOURCE_CLAIMS','COMPOSITE_TRACK_SCOPE_UNRESOLVED'} & set(r['model_review_flags'].split(' | '))) for r in elementary if r['has_numerical_allocation_model']),
                denominator_status='not_established' if not elementary else 'partial_grade_review_needed' if unknown else 'classified_working_inventory',
                statewide_completeness='not_established',
                interpretation='School-level model availability across cited source periods. Includes schools serving any K-5 grade, including K-8 and 3-6; excludes schools starting grade 6+. Counts a reported allocation combination totaling 100, full immersion, or an accepted quantified equal-day/minute plan. Not exact K timetables, all-strand completeness, named-language shares or tested-cohort exposure.'))
    return details,summary


def render_reports(root,tables):
    details,summary=report_rows(tables)
    followup=root/'config/research_migrations/ut_tx_allocations_2026_11_05.json'
    prefix=json.loads(followup.read_text()).get('elementary_report_prefix',PREFIX) if followup.exists() else PREFIX
    return {prefix+'_by_school.csv':csv_text(details),prefix+'_by_state.csv':csv_text(summary),
            prefix+'_reference_by_state.csv':csv_text([r for r in summary if r['audit_scope']=='reference_working_set']),
            prefix+'_all_records_by_state.csv':csv_text([r for r in summary if r['audit_scope']=='all_recorded_programme_hosts'])}
