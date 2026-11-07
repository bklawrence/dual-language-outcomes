"""Reviewed reference-use bounds, kept separate from source and policy dates."""
import json
import re


def reference_bounds(tables, *, latest=False):
    bounds={}
    for claim in tables['evidence_claims']:
        if claim['attribute']!='reviewed_record_reference_scope':continue
        review=json.loads(claim['reported_value'])
        field='latest_reviewed_selection_year' if latest else 'earliest_reviewed_selection_year'
        year=review.get(field)
        if not year:continue
        if not re.fullmatch(r'\d{4}-\d{2}',year):
            raise ValueError('Invalid reviewed reference-use bound')
        if latest and year<review['earliest_reviewed_selection_year']:
            raise ValueError('Reversed reviewed reference-use window')
        for key in review['evidence_ids']:
            pair=(review['evidence_table'],key)
            if pair in bounds and bounds[pair]!=year:
                raise ValueError('Conflicting reviewed reference-use bounds')
            bounds[pair]=year
    return bounds


def scoped_row(table,key,row,bounds,upper_bounds=None):
    lower=bounds.get((table,row[key]))
    upper=(upper_bounds or {}).get((table,row[key]))
    if not lower and not upper:return row
    value=dict(row)
    if lower:value['_earliest_reviewed_selection_year']=lower
    if upper:value['_latest_reviewed_selection_year']=upper
    return value


def within_reviewed_reference(row,year):
    return not year or (row.get('_earliest_reviewed_selection_year','')<=year
                        <=row.get('_latest_reviewed_selection_year','9999-99'))
