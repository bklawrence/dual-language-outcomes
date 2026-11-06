"""Reviewed ND/SD/MN/IA/MO/AK/HI inventory, including screened-only states."""
import hashlib
import json

from ..io import record_id
from .western_plains import migrate_state

STATES = {'ND', 'SD', 'MN', 'IA', 'MO', 'AK', 'HI'}
BASE = 'data/registry/northern_central_ak_hi_2026_11_05'


def school_key(state, district, school):
    return f'NC-{state}-S-' + hashlib.sha256('|'.join([state, district, school]).encode()).hexdigest()[:12]


def membership(b, state, school, district, source, locator, *, year=None):
    if district.startswith(('Public charter operator:', 'Private operator:', 'Tribal operator:')):
        b.claim('school', school, 'operator_or_source_reporting_group_not_verified_LEA', district,
                source, locator + ':reporting_group', year=year, status='metadata_only',
                notes='Cited operator, not a verified LEA. No district/authorizer crosswalk inferred.')
        return
    did = record_id('district', state, district)
    b.district(did, state, district, source, namespace='NC_research_district_name', native_id=district,
               status='provisional_name_group')
    b.membership(school, did, source, locator, year=year)


def migrate_reviewed_state(build, state):
    audit = json.loads(build.track_input('config/research_migrations/northern_central_ak_hi_2026_11_05.json').read_text())
    for path in audit['preserved_reports']:
        build.track_input(path)
    migrate_state(build, state, inventory=dict(states=STATES, base=BASE,
        dataset_suffix='_NORTHERN_CENTRAL_AK_HI_STRUCTURAL', namespace='NC',
        school_key=school_key, membership=membership,
        screening_attribute='northern_central_screening_observation',
        batch_description='seven-state structural first pass'))
