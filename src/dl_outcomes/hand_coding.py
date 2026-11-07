"""Validated, append-only researcher decisions submitted by the review website."""
from collections import defaultdict
from datetime import datetime, timezone
import base64
import gzip
import io
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit
import uuid

from .baseline import csv_text, json_text
from .gap_pilot import add_scope
from .io import digest, record_id

CONFIG = 'config/hand_coding.json'
JOURNAL = 'data/registry/hand_coded_reviews'
DATASET = 'RESEARCHER_HAND_CODED_REVIEWS'
SELECTION_ATTRIBUTE = 'hand_coded_structural_field_selection'
VARIABLES = {'delivery_structure', 'population_model', 'elementary_allocation_model', 'instruction_languages'}
CHOICES = {'delivery_structure': {'whole_school', 'strand', 'mixed'}, 'population_model': {'one_way', 'two_way'}}
CODING_METHODS = {'explicit_source_statement', 'researcher_interpretation', 'not_recorded'}
MARKER = re.compile(r'<!--\s*DL_REVIEW_V1:([A-Za-z0-9_-]+)\s*-->')


def year(value):
    return bool(isinstance(value, str) and re.fullmatch(r'20\d{2}-\d{2}', value)
                and int(value[-2:]) == (int(value[:4])+1)%100 and '2000-01' <= value <= '2035-36')


def identifier(value):
    try:
        return str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def web_url(value):
    if not isinstance(value,str):return False
    try:
        p = urlsplit(value)
        return p.scheme in {'http', 'https'} and bool(p.hostname) and not p.username and not p.password and len(value) <= 2048 and not re.search(r'\s',value)
    except (ValueError, TypeError):
        return False


def allocation_grade_scope(value):
    """Normalize unambiguous grade names; preserve the verbatim journal text."""
    value=re.sub(r'\bPRE[ -]?KINDERGARTEN\b','PK',value,flags=re.I)
    value=re.sub(r'\bKINDERGARTEN\b','K',value,flags=re.I)
    return re.sub(r'\bPRE[ -]?K\b','PK',value,flags=re.I)


def validate_record(record, sites, schools):
    """No name matching, inferred identities, blank-value overwrites or future-year backfill."""
    if not isinstance(record, dict) or not identifier(record.get('review_id')):
        raise ValueError('Every review needs a valid unique review ID.')
    sid = record.get('school_id')
    if not isinstance(sid,str) or sid not in schools:
        raise ValueError('The school is not an existing inventory identity.')
    if not year(record.get('reference_year')):
        raise ValueError('Choose a valid school year.')
    source_year = record.get('source_school_year')
    if source_year is not None and (not year(source_year) or source_year > record['reference_year']):
        raise ValueError('A source describing a later school year cannot support this reference year.')
    for field, limit in [('notes', 3000), ('source_quote', 3000), ('reviewer', 100), ('grade_scope', 120), ('source_locator', 200)]:
        if not isinstance(record.get(field, ''), str) or len(record.get(field, '')) > limit:
            raise ValueError('Review text exceeds its permitted length: ' + field)
    if not record.get('reviewer', '').strip():
        raise ValueError('Please enter the reviewer name.')
    if not isinstance(record.get('coding_method'),str) or record['coding_method'] not in CODING_METHODS:
        raise ValueError('Unknown coding basis; use not_recorded when the basis is cleared.')
    if not isinstance(record.get('disposition','coded'),str) or record.get('disposition', 'coded') not in {'coded', 'needs_review'}:
        raise ValueError('Unknown review disposition.')
    changes = record.get('changes')
    if not isinstance(changes, dict) or not set(changes) <= VARIABLES:
        raise ValueError('The review contains an unsupported variable.')
    event = record.get('program_event')
    if event is not None:
        from .review_events import KINDS
        if not isinstance(event, dict) or not isinstance(event.get('kind'),str) or event['kind'] not in KINDS:
            raise ValueError('Unknown program operating-status event.')
        if not year(event.get('first_school_year')) or event['first_school_year'] > record['reference_year']:
            raise ValueError('Choose the first supported school year, no later than this review year.')
        ids = event.get('site_ids')
        if (not isinstance(ids, list) or not ids or len(ids)>30 or any(not isinstance(i,str) for i in ids)
                or len(set(ids))!=len(ids) or any(i not in sites or sites[i]['school_id']!=sid for i in ids)):
            raise ValueError('Choose the program records at this school to which the status applies.')
        destination = event.get('destination_school_id')
        if destination is not None and (not isinstance(destination,str) or destination not in schools or destination==sid):
            raise ValueError('A move destination must be another existing school identity, or left unmatched.')
        for key, limit in [('destination_school_name',300),('destination_url',2048)]:
            if not isinstance(event.get(key,''),str) or len(event.get(key,''))>limit:
                raise ValueError('Invalid move destination details.')
        if event.get('destination_url') and not web_url(event['destination_url']):
            raise ValueError('Use an http(s) destination school URL.')
        if event['kind']!='moved' and (destination or event.get('destination_school_name') or event.get('destination_url')):
            raise ValueError('Destination details apply only to a moved program.')
    if record.get('disposition', 'coded') == 'coded' and not changes and not event:
        raise ValueError('Select at least one variable to save.')
    if record.get('disposition', 'coded') == 'needs_review' and (changes or event):
        raise ValueError('A parked case cannot change structural values; save a coded review instead.')
    if (changes or event) and not web_url(record.get('evidence_url')):
        raise ValueError('A coding decision needs an http(s) evidence URL.')
    if record.get('evidence_url') and not web_url(record['evidence_url']):
        raise ValueError('The evidence URL is not valid.')
    for variable, change in changes.items():
        if not isinstance(change, dict):
            raise ValueError('Invalid variable decision.')
        ids = change.get('site_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 30 or any(not isinstance(v,str) for v in ids) or len(set(ids)) != len(ids):
            raise ValueError('Choose the program(s) to which each decision applies.')
        if any(site not in sites or sites[site]['school_id'] != sid for site in ids):
            raise ValueError('A review cannot cross school or program identities.')
        value = change.get('value')
        if variable in CHOICES and (not isinstance(value,str) or value not in CHOICES[variable]):
            raise ValueError('Unsupported value for ' + variable)
        if variable == 'elementary_allocation_model':
            from .elementary_audit import elementary_scope
            if not isinstance(value, str) or not re.fullmatch(r'\d{1,3}(?:\.\d+)?/\d{1,3}(?:\.\d+)?', value):
                raise ValueError('Use an allocation label such as 90/10 or 50/50.')
            shares = list(map(float, value.split('/')))
            if any(v < 0 or v > 100 for v in shares) or abs(sum(shares)-100) > .001:
                raise ValueError('The two allocation percentages must total 100.')
            if not record.get('grade_scope', '').strip():
                raise ValueError('Record the grades to which the allocation applies.')
            if elementary_scope(allocation_grade_scope(record['grade_scope'])) in {'secondary_6_plus','preschool_only'}:
                raise ValueError('This variable records elementary allocation models; retain secondary program details in the research notes.')
        if variable == 'instruction_languages':
            if not isinstance(value, list) or not 1 <= len(value) <= 8 or any(not isinstance(v, str) or not v.strip() or len(v)>80 for v in value):
                raise ValueError('List the explicitly documented instructional languages.')
        if variable == 'delivery_structure' and value == 'mixed' and not record.get('notes', '').strip():
            raise ValueError('Explain the grade or program differences for a mixed model.')
    return record


def decode_submission(body):
    markers = MARKER.findall(body or '')
    if len(markers) != 1 or len(markers[0]) > 18000:
        raise ValueError('The submission has no single valid review payload.')
    encoded = markers[0]
    try:
        compressed = base64.urlsafe_b64decode(encoded + '='*((-len(encoded))%4))
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('The review batch is too large.')
        payload = json.loads(raw)
    except (OSError, ValueError, TypeError, EOFError, RecursionError) as exc:
        raise ValueError('The review payload is invalid or exceeds the size limit.') from exc
    if (not isinstance(payload, dict) or payload.get('version') != 1 or not identifier(payload.get('batch_id'))
            or not isinstance(payload.get('records'), list) or not 1 <= len(payload['records']) <= 10):
        raise ValueError('Unsupported review batch.')
    return payload


def accept_issue(root, event):
    """Called only by the trusted issues workflow; never execute issue text."""
    from .validation import load
    config = json.loads((root/CONFIG).read_text())
    issue = event['issue']; actor = issue['user']['login']
    if actor.lower() not in {u.lower() for u in config['authorized_reviewers']}:
        raise ValueError('This GitHub account is not an authorized dataset reviewer.')
    payload = decode_submission(issue.get('body', ''))
    if any(not isinstance(r,dict) for r in payload['records']):
        raise ValueError('Each review must be a structured record.')
    for record in payload['records']:
        for key in ['notes','source_quote']:
            if isinstance(record.get(key),str):record[key]=record[key].replace('\r\n','\n').replace('\r','\n')
    _, tables = load(root)
    sites = {r['site_id']: r for r in tables['program_sites']}
    schools = {r['school_id']: r for r in tables['schools']}
    for record in payload['records']:
        validate_record(record, sites, schools)
    if len({r['review_id'] for r in payload['records']}) != len(payload['records']):
        raise ValueError('A batch contains duplicate review IDs.')
    path = root/JOURNAL/(payload['batch_id']+'.json')
    if path.exists():
        old = json.loads(path.read_text())
        if old['records'] != payload['records'] or old['submission']['github_actor'].lower() != actor.lower():
            raise ValueError('This batch ID already exists with different content.')
        return {'status': 'already_saved', 'path': str(path.relative_to(root)), 'batch_id': payload['batch_id']}
    existing_ids = {r['review_id'] for p in (root/JOURNAL).glob('*.json') for r in json.loads(p.read_text())['records']}
    if existing_ids & {r['review_id'] for r in payload['records']}:
        raise ValueError('A review in this batch was already submitted; refresh the website before republishing.')
    payload['submission'] = dict(github_actor=actor, issue_number=issue['number'], issue_url=issue['html_url'],
                                 submitted_at=issue['created_at'], received_at=datetime.now(timezone.utc).isoformat(), hand_coded=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_text(payload))
    return {'status': 'saved', 'path': str(path.relative_to(root)), 'batch_id': payload['batch_id']}


def batches(root):
    return [(p, json.loads(p.read_text())) for p in sorted((root/JOURNAL).glob('*.json'))]


def migrate(build):
    if not (build.root/CONFIG).exists():
        return
    config = json.loads(build.track_input(CONFIG).read_text())
    for path in config['preserved_reports']:
        if digest(build.track_input(path)) != config['preserved_reports'][path]:
            raise ValueError('A pre-app report was altered: ' + path)
    readme = build.root/JOURNAL/'README.md'
    if readme.exists(): build.track_input(readme)
    sites = {r['site_id']:r for r in build.rows('program_sites')}
    schools = {r['school_id']:r for r in build.rows('schools')}
    seen = set()
    for path, batch in batches(build.root):
        build.track_input(path)
        submission = batch['submission']
        if submission['github_actor'].lower() not in {u.lower() for u in config['authorized_reviewers']}:
            raise ValueError('The journal contains an unauthorized reviewer.')
        build.dataset(DATASET, None, 'inventory', 'Researcher hand-coded structural evidence',
                      'repo:'+JOURNAL, publisher='Named dataset researchers',
                      notes='Hand-coded decisions; original observations retained; publisher webpages are linked, not asserted to be archived.')
        source = record_id('source', DATASET, digest(path))
        build.add('sources', source_id=source, dataset_id=DATASET,
                  source_url='https://github.com/'+config['repository']+'/blob/main/'+str(path.relative_to(build.root)),
                  version_label='hand_coded_batch_'+batch['batch_id'], retrieved_at=submission.get('received_at'),
                  snapshot_path=str(path.relative_to(build.root)), sha256=digest(path), snapshot_kind='saved_public_source',
                  notes='Saved researcher coding journal, not a publisher webpage snapshot. Original evidence URLs and coding method are retained in the review claims.')
        for sequence, record in enumerate(batch['records']):
            validate_record(record, sites, schools)
            if record['review_id'] in seen: raise ValueError('Duplicate hand-coded review ID.')
            seen.add(record['review_id'])
            metadata = dict(record, **submission, batch_id=batch['batch_id'], entry_method='hand_coded')
            build.claim('school',record['school_id'],'hand_coded_review',json_text(metadata),source,record['review_id'],
                        year=record['reference_year'],status='metadata_only',method='researcher_hand_coding',
                        notes='Human-authored coding. Reference year, source year, reviewer, authenticated author, evidence URL, notes and inference status are separate.')
            event = record.get('program_event')
            if event:
                from .review_events import ATTRIBUTE
                event_source = record_id('source', DATASET, digest(path), record['review_id'], 'program_event')
                build.add('sources', source_id=event_source, dataset_id=DATASET,
                          source_url='https://github.com/'+config['repository']+'/blob/main/'+str(path.relative_to(build.root)),
                          version_label='hand_coded_event_'+record['review_id'], retrieved_at=submission.get('received_at'),
                          snapshot_path=str(path.relative_to(build.root)), sha256=digest(path), snapshot_kind='saved_public_source',
                          notes='Dated researcher operating-status event; publisher evidence URL remains in the journal.')
                for site_id in event['site_ids']:
                    site = sites[site_id]
                    status_id = record_id('hand_coded_status', record['review_id'], site_id)
                    notes = 'HAND-CODED program '+event['kind']+'. Evidence: '+record['evidence_url']+'. '+record.get('notes','')
                    build.add('program_status_history', status_id=status_id, site_id=site_id,
                              school_year=event['first_school_year'], operating_status=event['kind'],
                              eligibility_status='not_operating_at_this_site' if event['kind']!='operating' else 'existing_inventory_eligibility_retained',
                              confirmation_method='researcher_hand_coding_'+record['coding_method'],
                              evidence_period_raw='First supported school year '+event['first_school_year'],
                              source_id=event_source, source_locator=record['review_id'], notes=notes)
                    fact=dict(event,site_id=site_id,school_id=record['school_id'],program_id=site['program_id'],
                              status_id=status_id,review_id=record['review_id'],reference_year=record['reference_year'],
                              supersedes_review_id=record.get('supersedes_review_id'),submitted_at=submission['submitted_at'],
                              issue_number=submission['issue_number'],batch_record_index=sequence,coding_method=record['coding_method'])
                    build.claim('program',site['program_id'],ATTRIBUTE,json_text(fact),event_source,record['review_id']+':'+site_id,
                                year=event['first_school_year'],status='metadata_only',method='researcher_hand_coding',notes=notes)
            for variable, change in record['changes'].items():
                for site_id in change['site_ids']:
                    site = sites[site_id]; locator = record['review_id']+':'+site_id+':'+variable
                    cid = record_id('hand_coded_evidence', locator); table = 'program_configurations'; ids = [cid]
                    notes = ('HAND-CODED by '+record['reviewer']+'. Review '+record['review_id']
                             +'. Evidence: '+record['evidence_url']+'. Reviewed grades: '+record.get('grade_scope','')
                             +'. Full notes and quotation retained in the hand_coded_review claim and source journal.')
                    status = 'documented' if record['coding_method']=='explicit_source_statement' else 'provisional'
                    period = record.get('source_school_year') or 'undated source; hand-coded review with separate reference-year bounds'
                    if variable in {'delivery_structure','population_model'}:
                        row = dict(configuration_id=cid,site_id=site_id,school_year=record.get('source_school_year'),
                                   grade_scope='not_reported',population_model='unknown',delivery_structure='unknown',
                                   program_kind='hand_coded_structural_observation',evidence_period_raw=period,
                                   verification_status=status,source_id=source,source_locator=locator,notes=notes)
                        row[variable]=change['value'];build.add(table,**row)
                    elif variable=='instruction_languages':
                        table='program_languages';ids=[]
                        for language in sorted(set(change['value'])):
                            common={n.casefold():n for n in ['English','Spanish','Mandarin','Chinese','French','German','Japanese','Korean','Arabic','Russian','Polish','Portuguese','Vietnamese','Somali','Hmong']}
                            language=common.get(language.strip().casefold(),language.strip())
                            lid=record_id('hand_coded_language',locator,language);ids.append(lid)
                            build.add(table,language_record_id=lid,site_id=site_id,language_name=language,language_role='instruction_language',
                                      valid_from_year=record.get('source_school_year'),valid_to_year=record.get('source_school_year'),
                                      evidence_period_raw=period,verification_status=status,source_id=source,source_locator=locator,notes=notes)
                    else:
                        from .baseline_selection import grade_set
                        table='allocation_schedules'
                        allocation_grades=allocation_grade_scope(record['grade_scope'])
                        build.add(table,schedule_id=cid,site_id=site_id,school_id=record['school_id'],school_year=record.get('source_school_year'),
                                  grade_scope=allocation_grades,reported_model_label=change['value'],
                                  percentage_basis='hand_coded_source_reported_model_label_language_order_and_instructional_denominator_not_established',
                                  schedule_status='reported_policy_requires_review',evidence_review_status='HAND_CODED_SOURCE_LABEL',
                                  grade_support_status='EXPLICIT_GRADE' if grade_set(allocation_grades) else 'PUBLISHED_MODEL_ONLY',tested_cohort_exposure='not_established',
                                  evidence_period_raw=period,source_id=source,source_locator=locator,notes=notes)
                    scope=dict(site_id=site_id,program_id=site['program_id'],school_id=record['school_id'],fact_id=locator,
                               reference_year=record['reference_year'],earliest_reviewed_selection_year=record['reference_year'],
                               latest_reviewed_selection_year=record['reference_year'])
                    add_scope(build,scope,table,ids,source)
                    review=dict(site_id=site_id,school_id=record['school_id'],program_id=site['program_id'],
                                selection_year=record['reference_year'],variable=variable,evidence_ids=ids,
                                submitted_at=submission['submitted_at'],issue_number=submission['issue_number'],
                                batch_record_index=sequence,review_id=record['review_id'],hand_coded=True,
                                reason='Hand-coded field selection by '+record['reviewer']+'; '+record['coding_method']+'. Review '+record['review_id'])
                    build.claim('program',site['program_id'],SELECTION_ATTRIBUTE,json_text(review),source,locator+':selection',
                                year=record['reference_year'],status='metadata_only',method='researcher_hand_coding',notes=notes)
    build.notes.append('Researcher hand-coded structural decisions are separately marked, cited and bounded to their reviewed school year; original observations and assessment data are retained.')


def selection_overrides(tables):
    decisions=defaultdict(list)
    for claim in tables['evidence_claims']:
        if claim['attribute']==SELECTION_ATTRIBUTE:
            value=json.loads(claim['reported_value'])
            decisions[(value['site_id'],value['selection_year'],value['variable'])].append(value)
    return {key:max(values,key=lambda v:(v['submitted_at'],v.get('issue_number',0),v.get('batch_record_index',0),v['review_id'])) for key,values in decisions.items()}


def allocation_overrides(tables):
    """All grade-specific reviews, newest first; latest-per-field loses grades."""
    decisions=defaultdict(list)
    for claim in tables['evidence_claims']:
        if claim['attribute']==SELECTION_ATTRIBUTE:
            value=json.loads(claim['reported_value'])
            if value['variable']=='elementary_allocation_model':
                decisions[(value['site_id'],value['selection_year'])].append(value)
    return {key:sorted(values,key=lambda v:(v['submitted_at'],v.get('issue_number',0),
                    v.get('batch_record_index',0),v['review_id']),reverse=True)
            for key,values in decisions.items()}


def revise_report_paths(root, contents, tables):
    config=json.loads((root/CONFIG).read_text());old=config['preserved_reports'];result={};aliases={}
    from hashlib import sha256
    for path,text in contents.items():
        target=path
        if path in old and sha256(text.encode()).hexdigest()!=old[path]:
            target='data/reports/hand_coding/current/revised/'+PurePosixPath(path).name;aliases[path]=target
        if target in result:raise ValueError('Hand-coding report filename collision.')
        result[target]=text
    records=[dict(review_id=r['review_id'],school_id=r['school_id'],reference_year=r['reference_year'],
                  hand_coded=True,reviewer=r['reviewer'],github_actor=b['submission']['github_actor'],
                  submitted_at=b['submission']['submitted_at'],coding_method=r['coding_method'],
                  evidence_url=r.get('evidence_url',''),notes=r.get('notes',''),source_quote=r.get('source_quote',''),
                  changes_json=json_text(r['changes']),program_event_json=json_text(r['program_event']) if r.get('program_event') else '',disposition=r.get('disposition','coded'))
             for _,b in batches(root) for r in b['records']]
    result['data/reports/hand_coding/current/reviews.csv']=csv_text(records,fields=['review_id','school_id','reference_year','hand_coded','reviewer','github_actor','submitted_at','coding_method','evidence_url','notes','source_quote','changes_json','program_event_json','disposition'])
    events=[]
    for _,batch in batches(root):
        for record in batch['records']:
            event=record.get('program_event')
            if not event:continue
            for site in event['site_ids']:
                events.append(dict(review_id=record['review_id'],site_id=site,school_id=record['school_id'],
                    kind=event['kind'],first_school_year=event['first_school_year'],reference_year=record['reference_year'],
                    destination_school_id=event.get('destination_school_id'),destination_school_name=event.get('destination_school_name',''),
                    destination_url=event.get('destination_url',''),reviewer=record['reviewer'],github_actor=batch['submission']['github_actor'],
                    coding_method=record['coding_method'],evidence_url=record['evidence_url'],notes=record.get('notes','')))
    result['data/reports/hand_coding/current/program_events.csv']=csv_text(events,fields=['review_id','site_id','school_id','kind','first_school_year','reference_year','destination_school_id','destination_school_name','destination_url','reviewer','github_actor','coding_method','evidence_url','notes'])
    # A live, selected programme CSV makes the effects visible without
    # modifying the frozen baseline or repeating long notes in every field.
    from .baseline import school_rows, programme_rows
    from .baseline_selection import Selection
    rules=json.loads((root/'data/baselines/national_structural_v1/rules.json').read_text())
    selection=Selection(tables,rules);reference=config['reference_year'];schools=[]
    for yr in sorted({reference,*rules['source_vintage_exceptions'].values()}):schools.extend(school_rows(selection,tables,yr))
    programmes,_,_,_=programme_rows(selection,tables,schools,reference)
    manual=selection_overrides(tables)
    for row in programmes:
        fields={v:r for (site,yr,v),r in manual.items() if site==row['site_id'] and yr==reference}
        row['hand_coded']=bool(fields)
        row['hand_coded_variables']=' | '.join(sorted(fields))
        row['hand_coded_review_ids']=' | '.join(sorted({r['review_id'] for r in fields.values()}))
    result['data/reports/hand_coding/current/programs.csv']=csv_text(programmes)
    result['data/reports/hand_coding/current/README.md']=(
        '# Live research views\n\n'
        '`programs.csv` is the selected '+reference+' program site view, with `hand_coded`, '
        '`hand_coded_variables` and `hand_coded_review_ids` flags. Program records are evidence groups, '
        'not guaranteed distinct programs. Operation, eligibility, source dates and missingness remain explicit.\n\n'
        '`reviews.csv` contains all published hand-coded reviews, including other reference years, '
        'researcher and authenticated GitHub account, timestamps, sources, notes, quotations and coding method. '
        'Immutable journal files are in `data/registry/hand_coded_reviews/`. Original observations and the '
        'frozen national baseline are retained. Reviewed-year bounds are not program start or end dates.\n')
    return result,aliases
