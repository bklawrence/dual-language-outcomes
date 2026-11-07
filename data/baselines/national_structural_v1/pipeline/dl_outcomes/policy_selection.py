"""Explicit current policy choices, with original source observations retained."""
import json

ATTRIBUTE = 'current_allocation_policy_selection'


def current_policy_choices(tables, year):
    sites = {r['site_id']: r for r in tables['program_sites']}
    schedules = {r['schedule_id']: r for r in tables['allocation_schedules']}
    selected = {}
    for claim in tables['evidence_claims']:
        if claim['attribute'] != ATTRIBUTE:
            continue
        choice = json.loads(claim['reported_value'])
        if choice['effective_from'] and year and choice['effective_from'] > year:
            continue
        site = sites.get(choice['site_id'])
        schedule = schedules.get(choice['selected_schedule_id'])
        if (claim['entity_type'] != 'program' or not site or not schedule
                or site['program_id'] != claim['entity_id']
                or choice['program_id'] != site['program_id']
                or choice['school_id'] != site['school_id']
                or schedule['site_id'] != site['site_id']
                or schedule['school_id'] != site['school_id']):
            raise ValueError('Reviewed policy choice changes school/programme/language scope')
        label = schedule['reported_model_label'].replace('-', '/').replace(':', '/').replace(' ', '')
        if choice['model'] != label:
            raise ValueError('Reviewed policy model does not match its selected source schedule')
        if site['site_id'] in selected:
            raise ValueError('Multiple current policy selections for one programme')
        selected[site['site_id']] = choice
    return selected
