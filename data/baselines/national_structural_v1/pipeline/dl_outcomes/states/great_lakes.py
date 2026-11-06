"""Reviewed WI/MI/IL/IN sources, reusing the original Illinois identities."""
import hashlib
import json

from ..io import record_id
from .western_plains import migrate_state

STATES = {'WI', 'MI', 'IL', 'IN'}
BASE = 'data/registry/great_lakes_2026_11_05'
AUDIT = 'config/research_migrations/great_lakes_2026_11_05.json'
SUFFIX = '_GREAT_LAKES_STRUCTURAL'


def school_key(state, district, school):
    return f'GL-{state}-S-' + hashlib.sha256('|'.join([state, district, school]).encode()).hexdigest()[:12]


def membership(b, state, school, district, source, locator, *, year=None):
    if district.startswith(('Public charter operator:', 'Private operator:', 'Tribal operator:')):
        b.claim('school', school, 'operator_or_source_reporting_group_not_verified_LEA', district,
                source, locator + ':reporting_group', year=year, status='metadata_only',
                notes='Operator/reporting group only; no unverified LEA or authorizer crosswalk manufactured.')
        return
    if school.startswith('IL-S') and any(r['school_id'] == school for r in b.rows('school_district_history')):
        b.claim('school', school, 'reviewed_reported_district_name', district, source, locator + ':district',
                status='documented', notes='Existing Illinois district membership retained; this is a source-name review, not a new official crosswalk.')
        return
    did = record_id('district', state, district)
    b.district(did, state, district, source, namespace='GL_research_district_name', native_id=district,
               status='provisional_name_group')
    b.membership(school, did, source, locator, year=year)


def migrate_reviewed_state(build, state):
    audit = json.loads(build.track_input(AUDIT).read_text())
    for path in audit['preserved_reports']:
        build.track_input(path)
    build.track_input(audit['legacy_rows_path'])
    decisions = json.loads(build.track_input(BASE + '/identity_decisions.json').read_text())
    aliases = {(d['state'], d['district'], d['school']): d['school_id']
               for d in decisions if d.get('school_id')}
    def identity(code, district, school):
        return aliases.get((code, district, school), school_key(code, district, school))
    migrate_state(build, state, inventory=dict(states=STATES, base=BASE,
        dataset_suffix=SUFFIX, namespace='GL', school_key=identity, membership=membership,
        reuse_existing_entities=True, screening_attribute='great_lakes_screening_observation',
        batch_description='four-state Great Lakes structural review'))
