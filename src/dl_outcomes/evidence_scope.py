"""Reviewed reference-use bounds, kept separate from source and policy dates."""
import json
import re


def reference_bounds(tables):
    bounds={}
    for claim in tables['evidence_claims']:
        if claim['attribute']!='reviewed_record_reference_scope':continue
        review=json.loads(claim['reported_value'])
        year=review['earliest_reviewed_selection_year']
        if not re.fullmatch(r'\d{4}-\d{2}',year):
            raise ValueError('Invalid reviewed reference-use bound')
        for key in review['evidence_ids']:
            pair=(review['evidence_table'],key)
            if pair in bounds and bounds[pair]!=year:
                raise ValueError('Conflicting reviewed reference-use bounds')
            bounds[pair]=year
    return bounds


def scoped_row(table,key,row,bounds):
    lower=bounds.get((table,row[key]))
    return dict(row,_earliest_reviewed_selection_year=lower) if lower else row


def within_reviewed_reference(row,year):
    return not year or row.get('_earliest_reviewed_selection_year','')<=year
