"""Apply reviewed allocation changes only to their explicitly described grades."""


def remaining_scopes(row, occupied):
    from .baseline_selection import grade_set
    grades = grade_set(row['grade_scope'])
    if grades is None:
        return []
    remaining = sorted(grades - occupied)
    if set(remaining) == grades:
        return [row]
    groups = []
    for grade in remaining:
        if groups and grade == groups[-1][-1] + 1:
            groups[-1].append(grade)
        else:
            groups.append([grade])
    def label(grade):
        return 'PK' if grade == -1 else 'K' if grade == 0 else str(grade)
    return [dict(row, grade_scope=label(g[0]) if len(g)==1 else label(g[0])+'-'+label(g[-1]),
                 _source_grade_scope=row.get('_source_grade_scope',row['grade_scope'])) for g in groups]


def apply_grade_reviews(rows, reviews, base, year):
    from .baseline_selection import grade_set, select_rows
    selected, occupied = [], set()
    for review in reviews:
        candidates, _ = select_rows(rows, year, override_ids=review['evidence_ids'])
        for row in candidates:
            grades = grade_set(row['grade_scope'])
            if grades is None:
                # An unbounded newer review cannot be assigned to particular
                # grades. Preserve its former whole-field selection semantics.
                return selected or [row]
            selected.extend(remaining_scopes(row, occupied))
            occupied.update(grades)
    # Keep conflicts between unreviewed source policies visible. Only grades
    # explicitly covered by a manual decision are removed from those policies.
    for row in base:
        selected.extend(remaining_scopes(row, occupied))
    return selected
