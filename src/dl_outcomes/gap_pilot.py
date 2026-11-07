"""Append reviewed pilot evidence and audit a fixed, existing research sample."""
from collections import Counter, defaultdict
import json

from .baseline import AVAILABLE, RESOLVED, csv_text, json_text, load_snapshot, school_rows
from .baseline_selection import Selection, VARIABLES, later_period_mention, REJECTED_GRADE
from .elementary_audit import elementary_scope, numeric_model
from .contracts import catalog
from .io import digest, record_id, read_csv

CONFIG = 'config/research_migrations/structural_gaps_pilot_2026_11_06.json'
DATASET = 'STRUCTURAL_GAPS_PILOT_2026_11_06'
RECORD_SCOPE = 'reviewed_record_reference_scope'
FIELD_REVIEW = 'reviewed_structural_field_selection'
LANGUAGE_CODES = {'English':'en','Spanish':'es','Vietnamese':'vi','Mandarin':'cmn'}


def inputs(root):
    config = json.loads((root / CONFIG).read_text())
    base = root / config['base']
    return config, {p.stem: json.loads(p.read_text()) for p in base.glob('*.json')}


def add_scope(build, fact, table, ids, source):
    value = dict(evidence_table=table, evidence_ids=ids,
        site_id=fact['site_id'], program_id=fact['program_id'], school_id=fact['school_id'],
        earliest_reviewed_selection_year=fact['earliest_reviewed_selection_year'],
        interpretation='Reference-use bound, not a source date or a policy start date.')
    if fact.get('latest_reviewed_selection_year'):
        value['latest_reviewed_selection_year']=fact['latest_reviewed_selection_year']
        value['interpretation']+=' The upper review bound does not establish a programme or policy end date.'
    entity, key = ('program', fact['program_id']) if fact['program_id'] else ('school', fact['school_id'])
    build.claim(entity, key, RECORD_SCOPE, json_text(value), source,
        fact['fact_id'] + ':reference_scope', year=fact['reference_year'],
        status='metadata_only', method='reference_applicability_review',
        notes='The source observation retains its actual year/undated status. This review does not authorize use before the reviewed reference.')


def migrate(build):
    config, files = inputs(build.root)
    build.track_input(CONFIG)
    base = build.root / config['base']
    for path in sorted(base.rglob('*')):
        if path.is_file() and path.suffix in {'.json','.txt'}:
            build.track_input(path)
    # These receipts are also real offline dependencies: the comparison reads
    # the frozen evidence and preservation audits read the archived reports.
    for path in set(files['preservation']['preserved_files']) | set(files['preservation']['preserved_assessment_context_outputs']):
        build.track_input(path)
    build.dataset(DATASET, None, 'inventory', 'Nine-district structural gap pilot',
        'repo:' + config['base'], notes=config['scope'])
    sources = {}
    for doc in files['sources']:
        sources[doc['key']] = build.source_file(DATASET, doc['path'], metadata=doc['metadata_path'])
        build.track_input(doc['extraction_path'])
    sites = {r['site_id']:r for r in build.rows('program_sites')}
    schools = {r['school_id']:r for r in build.rows('schools')}
    selected = defaultdict(list)
    for fact in files['observations']:
        source = sources[fact['source_keys'][0]]
        fid = fact['fact_id']; sid = fact['school_id']; site = fact['site_id']
        if sid not in schools or schools[sid]['state_code'] != fact['state']:
            raise ValueError('Pilot changes a reviewed school identity: ' + fid)
        if site and (site not in sites or sites[site]['school_id'] != sid
                     or sites[site]['program_id'] != fact['program_id']):
            raise ValueError('Pilot changes programme/school attribution: ' + fid)
        variable = fact['variable']; ids = []; table = None
        note = fact['notes'] + ' Source quote: ' + fact['source_quote']
        common = dict(site_id=site, source_id=source, source_locator=fid,
            evidence_period_raw=fact['evidence_period_raw'], notes=note)
        if variable in {'population_model','delivery_structure','programme_grade_scope'}:
            table = 'program_configurations'; ids = [record_id('configuration', DATASET, fid)]
            row = dict(configuration_id=ids[0], school_year=fact['source_school_year'],
                grade_scope='not_reported', population_model='unknown', delivery_structure='unknown',
                program_kind='reviewed_structural_selection_with_separate_source_dates',
                verification_status='documented', **common)
            row[{'programme_grade_scope':'grade_scope'}.get(variable,variable)] = fact['value']
            build.add(table, **row)
        elif variable == 'instruction_languages':
            table = 'program_languages'
            for language in fact['value']:
                lid = record_id('language', DATASET, fid, language); ids.append(lid)
                build.add(table, language_record_id=lid, site_id=site, language_name=language,
                    language_code=LANGUAGE_CODES.get(language), language_role='instruction_language',
                    valid_from_year=fact['source_school_year'], valid_to_year=fact['source_school_year'],
                    evidence_period_raw=fact['evidence_period_raw'], verification_status='documented',
                    source_id=source, source_locator=fid, notes=note)
        elif variable == 'elementary_allocation_model':
            table = 'allocation_schedules'; ids = [record_id('schedule', DATASET, fid)]
            build.add(table, schedule_id=ids[0], school_id=sid, school_year=fact['source_school_year'],
                grade_scope=fact['grade_scope'], reported_model_label=fact['value'],
                percentage_basis=fact['percentage_basis'], schedule_status=fact['schedule_status'],
                evidence_review_status='CORE_SCOPE_ONLY' if 'core' in fact['percentage_basis'].lower() else 'PILOT_SOURCE_SCOPE_REVIEWED',
                grade_support_status=('DISTRICT_GRADE_BAND_MODEL' if fact['source_keys'][0] in {'alief_one','austin_es'}
                    else 'EXPLICIT_GRADE' if fact['shares'] else 'PUBLISHED_MODEL_ONLY'),
                tested_cohort_exposure='not_established', **common)
            for language, share in fact['shares'].items():
                build.add('instructional_allocations', allocation_id=record_id('allocation', ids[0], language),
                    schedule_id=ids[0], language_name=language, language_code=LANGUAGE_CODES.get(language),
                    instruction_share_pct=share,
                    evidence_type='researcher_inference' if fact['schedule_status']=='inferred_plan' else 'documented_plan',
                    source_id=source, source_locator=fid)
        elif variable == 'reference_operation':
            # Existing annual reviews survive unchanged; an extra affirmative
            # review is unnecessary when the same reference is already covered.
            current = [r for r in build.rows('program_status_history')
                       if r['site_id']==site and r['school_year']==fact['reference_year']]
            if not current:
                table = 'program_status_history'; ids = [record_id('status', DATASET, fid)]
                build.add(table, status_id=ids[0], site_id=site, school_year=fact['reference_year'],
                    operating_status=fact['value'], eligibility_status='documented_public_academic_immersion',
                    instructional_scope='academic_content_in_two_languages', public_funding_status='public_district_school',
                    confirmation_method=fact['method'], evidence_period_raw=fact['evidence_period_raw'],
                    source_id=source, source_locator=fid, notes=note)
        elif variable in {'campus_delivery_structure','campus_programme_change','allocation_description_requires_review'}:
            entity, key = ('program', fact['program_id']) if site else ('school', sid)
            attribute = 'reported_delivery_structure' if variable=='campus_delivery_structure' else variable
            value = dict(structure_class=fact['value'], fact_id=fid) if variable=='campus_delivery_structure' else fact['value']
            build.claim(entity,key,attribute,json_text(value),source,fid,
                year=fact['source_school_year'],period=fact['evidence_period_raw'],
                status='documented' if variable!='allocation_description_requires_review' else 'provisional',
                method=fact['method'],notes=note)
            table = 'evidence_claims'; ids = [record_id('claim',entity,key,attribute,source,fid)]
        else:
            raise ValueError('Unknown pilot variable: '+variable)
        if ids:
            add_scope(build,fact,table,ids,source)
        metadata = dict(fact, canonical_evidence_table=table, canonical_evidence_ids=ids,
            supporting_source_ids=[sources[k] for k in fact['source_keys']])
        entity, key = ('program',fact['program_id']) if site else ('school',sid)
        build.claim(entity,key,'structural_gap_pilot_observation',json_text(metadata),source,
            fid+':review',year=fact['reference_year'],status='metadata_only',method='field_specific_research_review',
            notes='Reference review, evidence dates, source chain, scope and inference method retained separately.')
        if variable in VARIABLES and variable!='reference_operation' and site and ids:
            selected[(site,fact['reference_year'],variable)].append((fact,ids,source))
    for (site,year,variable), decisions in selected.items():
        fact = decisions[0][0]
        value = dict(site_id=site,program_id=fact['program_id'],school_id=fact['school_id'],
            selection_year=year,variable=variable,evidence_ids=sorted({key for _,ids,_ in decisions for key in ids}),
            reason='Reviewed pilot field selection. Original observations retained. '+ ' '.join(f['notes'] for f,_,_ in decisions))
        build.claim('program',fact['program_id'],FIELD_REVIEW,json_text(value),decisions[0][2],
            site+':'+year+':'+variable,year=year,status='metadata_only',method='field_specific_reference_selection',
            notes='Selects source-scoped evidence without converting undated policies into new annual observations.')
    build.notes.append(config['scope']+' Source-year bounds and field review claims are not policy start dates or student exposure.')


def audit_errors(root,tables):
    config, files = inputs(root); errors=[]
    for path, expected in files['preservation']['preserved_files'].items():
        if digest(root/path)!=expected:errors.append('Pilot changed frozen/archived file: '+path)
    for path, expected in files['preservation']['preserved_assessment_context_outputs'].items():
        if digest(root/path)!=expected:errors.append('Pilot changed assessment/context output: '+path)
    schema, original = load_snapshot(root/'data/baselines/national_structural_v1')
    for table in files['preservation']['original_structural_tables']:
        key=schema['$defs'][table]['x-primary-key']
        actual={tuple(r[k] for k in key):r for r in tables[table]}
        for row in original[table]:
            if actual.get(tuple(row[k] for k in key))!=row:
                errors.append('Pilot removed/changed an original evidence row: '+table);break
    benchmark=files['baseline_programme_records']
    sites={r['site_id']:r for r in tables['program_sites']}
    if set(sites)!={r['site_id'] for r in original['program_sites']}:
        errors.append('Pilot added/removed programme identities outside its scope')
    known_sources={d['key'] for d in files['sources']}
    for fact in files['observations']:
        if not set(fact['source_keys'])<=known_sources:errors.append('Pilot source chain incomplete: '+fact['fact_id'])
        if fact['site_id'] and (sites[fact['site_id']]['school_id']!=fact['school_id'] or sites[fact['site_id']]['program_id']!=fact['program_id']):
            errors.append('Pilot evidence crosses school/programme identity: '+fact['fact_id'])
        if fact['shares'] and abs(sum(fact['shares'].values())-100)>0.01:
            errors.append('Pilot shares do not total 100: '+fact['fact_id'])
        if fact['source_school_year'] and fact['source_school_year']>fact['reference_year']:
            errors.append('Pilot backdates a source-year observation: '+fact['fact_id'])
    if len({r['district_key'] for r in benchmark})!=9:errors.append('Pilot no longer covers its nine fixed districts')
    return errors


def comparison(root,tables):
    config, files=inputs(root)
    _, old=load_snapshot(root/'data/baselines/national_structural_v1')
    rules=json.loads((root/'data/baselines/national_structural_v1/rules.json').read_text())
    selections=[Selection(old,rules),Selection(tables,rules)]
    states={'TX','NC','NM'}; year=config['reference_year']
    school_views=[{r['school_id']:r for r in school_rows(s,ts,year,states=states)}
                  for s,ts in zip(selections,[old,tables])]
    selected=files['baseline_programme_records']
    by_school=defaultdict(list)
    field_rows=[]; school_output=[]
    values_by_stage=[]
    for stage,(selection,ts,sv) in enumerate(zip(selections,[old,tables],school_views)):
        site_index={r['site_id']:r for r in ts['program_sites']}; collected={}
        for row in selected:
            site=site_index[row['site_id']]; school=sv[row['school_id']]
            fields={}
            for variable in VARIABLES:
                if variable=='reference_operation':field,_=selection.operation_field(site,year)
                elif variable=='elementary_allocation_model':
                    field,_=selection.select_allocations(site,year,school['school_level'],json.loads(fields['programme_grade_scope']['value_json']))
                else:field,_=selection.select_field(site,variable,year)
                fields[variable]=field
                collected[(site['site_id'],variable)]=field
        values_by_stage.append(collected)
    for row in selected:
        by_school[row['school_id']].append(row)
        for variable in VARIABLES:
            before=values_by_stage[0][(row['site_id'],variable)]
            after=values_by_stage[1][(row['site_id'],variable)]
            field_rows.append(dict(district_key=row['district_key'],state=row['state_code'],school_id=row['school_id'],
                school_name=row['school_name'],site_id=row['site_id'],variable=variable,reference_year=year,
                before_status=before['value_status'],after_status=after['value_status'],
                before_value_json=before['value_json'],after_value_json=after['value_json'],
                before_applicability=before['applicability'],after_applicability=after['applicability'],
                before_evidence_ids=before['selected_evidence_ids'],after_evidence_ids=after['selected_evidence_ids'],
                before_source_ids=before['selected_source_ids'],after_source_ids=after['selected_source_ids'],
                after_temporal_status=after['temporal_status'],reason=after['reason']))
    for sid,rows in sorted(by_school.items()):
        entry=dict(district_key=rows[0]['district_key'],state=rows[0]['state_code'],school_id=sid,school_name=rows[0]['school_name'],
            reference_year=year,school_level=school_views[0][sid]['school_level'],elementary_denominator=int(school_views[0][sid]['school_level']=='elementary'))
        for i,tag in enumerate(['before','after']):
            available=[]
            for row in rows:
                field=values_by_stage[i][(row['site_id'],'elementary_allocation_model')]
                if field['value_status'] in AVAILABLE:available.extend(json.loads(field['value_json']))
            for schedule in selections[i].campus_allocations[sid]:
                if (not later_period_mention(schedule,year) and
                        schedule['grade_support_status'] not in REJECTED_GRADE and
                        elementary_scope(schedule['grade_scope']) not in {'secondary_6_plus','preschool_only'} and
                        (numeric_model(schedule['reported_model_label']) or selections[i].shares[schedule['_id']])):
                    available.append(dict(model_label=schedule['reported_model_label'],percentage_basis=schedule['percentage_basis']))
            campus=school_views[i][sid]
            entry[tag+'_has_primary_model']=int(bool(available)) if entry['elementary_denominator'] else 0
            entry[tag+'_model_labels']=' | '.join(sorted({v['model_label'] for v in available if v['model_label']}))
            entry[tag+'_percentage_bases']=' | '.join(sorted({v['percentage_basis'] for v in available}))
            entry[tag+'_campus_structure']=campus['campus_structure_evidence_classes']
            entry[tag+'_confirmed_reference_host']=int(any(selections[i].operation(next(s for s in (old if i==0 else tables)['program_sites'] if s['site_id']==r['site_id']),year)['confirmed_qualifying'] for r in rows))
        school_output.append(entry)
    summaries=[]
    for review in files['district_reviews']:
        district=review['district_key']; sr=[r for r in school_output if r['district_key']==district and r['elementary_denominator']]
        entry=dict(district_key=district,state=review['state'],district=review['district'],reference_year=year,
            fixed_baseline_school_identities=review['baseline_school_identities'],fixed_baseline_programme_site_records=review['baseline_programme_site_records'],
            elementary_school_identities=len(sr),before_with_primary_model=sum(r['before_has_primary_model'] for r in sr),
            after_with_primary_model=sum(r['after_has_primary_model'] for r in sr),
            newly_with_primary_model=sum(not r['before_has_primary_model'] and r['after_has_primary_model'] for r in sr),
            checked_archived_sources=len(review['checked_archived_source_keys']),
            appended_observations=sum(r['district_key']==district for r in files['observations']),
            schools_with_new_observations=len({f['school_id'] for f in files['observations'] if f['district_key']==district}),
            before_confirmed_reference_hosts=sum(r['before_confirmed_reference_host'] for r in school_output if r['district_key']==district),
            after_confirmed_reference_hosts=sum(r['after_confirmed_reference_host'] for r in school_output if r['district_key']==district),
            interpretation='Fixed research identities, all reference-2025-26 selections. Includes unconfirmed candidates; not a district census or the older Texas source-year denominator.')
        summaries.append(entry)
    completeness=[]
    for district in ['ALL']+[r['district_key'] for r in files['district_reviews']]:
        for variable in VARIABLES:
            rr=[r for r in field_rows if r['variable']==variable and (district=='ALL' or r['district_key']==district)]
            out=dict(district_key=district,variable=variable,programme_site_records=len(rr))
            for stage in ['before','after']:
                applicable=[r for r in rr if r[stage+'_applicability']=='applicable']
                out[stage+'_applicable']=len(applicable)
                out[stage+'_with_evidence']=sum(r[stage+'_status'] in AVAILABLE for r in applicable)
                out[stage+'_resolved']=sum(r[stage+'_status'] in RESOLVED for r in applicable)
            out['newly_resolved']=sum(r['before_status'] not in RESOLVED and r['after_status'] in RESOLVED and r['after_applicability']=='applicable' for r in rr)
            completeness.append(out)
    return field_rows,school_output,summaries,completeness


def render_reports(root,tables):
    config,files=inputs(root)
    errors=audit_errors(root,tables)
    if errors:raise ValueError('\n'.join(errors[:30]))
    fields,schools,districts,completeness=comparison(root,tables)
    primary=[r for r in schools if r['elementary_denominator']]
    summary=dict(research_date=config['research_date'],reference_year=config['reference_year'],
        districts=len(districts),fixed_school_research_identities=len(schools),
        fixed_programme_site_evidence_records=len({r['site_id'] for r in fields}),
        elementary_school_identities=len(primary),
        before_with_primary_model=sum(r['before_has_primary_model'] for r in primary),
        after_with_primary_model=sum(r['after_has_primary_model'] for r in primary),
        newly_with_primary_model=sum(not r['before_has_primary_model'] and r['after_has_primary_model'] for r in primary),
        appended_observations=len(files['observations']),schools_with_new_observations=len({f['school_id'] for f in files['observations']}),
        archived_source_receipts=len(files['sources']),review_cases=len(files['review_cases']),
        new_identity_merges=0,new_assessment_collection=False,frozen_baseline_unchanged=True,
        comparison_interpretation='Same existing research identities at 2025-26 before and after. Texas baseline target-year selections are compared, not its 2023-24 source-vintage working denominator. Core-only ratios and published model labels remain separately typed; this is not national census coverage.')
    prefix=config['report_prefix']
    observations=[dict(fact_id=f['fact_id'],district_key=f['district_key'],state=f['state'],school_id=f['school_id'],
        school_name=f['school_name'],site_id=f['site_id'],variable=f['variable'],value_json=json.dumps(f['value'],ensure_ascii=False),
        grade_scope=f['grade_scope'],source_school_year=f['source_school_year'],reference_year=f['reference_year'],
        evidence_period_raw=f['evidence_period_raw'],earliest_reviewed_selection_year=f['earliest_reviewed_selection_year'],
        method=f['method'],percentage_basis=f['percentage_basis'],schedule_status=f['schedule_status'],
        source_keys=' | '.join(f['source_keys']),source_quote=f['source_quote'],notes=f['notes']) for f in files['observations']]
    source_index={r['key']:r for r in files['sources']}
    cases=[dict(case_id=c['case_id'],state=c['state'],district=c['district'],schools=c['schools'],issue=c['issue'],
        recorded_decision=c['recorded_decision'],status=c['status'],
        source_urls=' | '.join(source_index[k]['url'] for k in c['source_keys'])) for c in files['review_cases']]
    sources=[dict(key=s['key'],title=s['title'],url=s['url'],snapshot_path=s['path'],sha256=s['sha256'],
        observations_supported=sum(s['key'] in f['source_keys'] for f in files['observations']),
        use='supports_observations' if any(s['key'] in f['source_keys'] for f in files['observations']) else 'screened_not_used_for_classification') for s in files['sources']]
    contents={prefix+'.json':json_text(summary),prefix+'_by_district.csv':csv_text(districts),
        prefix+'_school_comparison.csv':csv_text(schools),prefix+'_field_comparison.csv':csv_text(fields),
        prefix+'_completeness.csv':csv_text(completeness),prefix+'_observations.csv':csv_text(observations),
        prefix+'_review_cases.csv':csv_text(cases),prefix+'_sources.csv':csv_text(sources)}
    return contents,summary


def revise_report_paths(root,contents):
    """Give changed derived reports a new path; retain every earlier receipt."""
    config,files=inputs(root)
    previous=files['preservation']['preserved_prior_reports']
    revised={};aliases={}
    from hashlib import sha256
    from pathlib import PurePosixPath
    for path,text in contents.items():
        target=path
        if path in previous and sha256(text.encode()).hexdigest()!=previous[path]:
            # Some earlier derived school views live beside their registry
            # inputs. They are registered reports too; preserve their old
            # receipt and publish the recomputed view under the new namespace.
            target=config['revised_report_directory']+'/'+PurePosixPath(path).name
            aliases[path]=target
        if target in revised:raise ValueError('Revised report filename collision: '+target)
        revised[target]=text
    return revised,aliases
