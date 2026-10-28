
# National Dual-Language Program Registry

This directory contains the master registry for a
longitudinal study of Spanish-English dual-language
education in the United States.

## Core datasets

### schools.csv
One record per school.

Includes a stable research ID, school name, state,
district, NCES identifier, and verification status.

### programs.csv
One record per dual-language program.

Includes a stable program ID, language pair,
one-way or two-way designation, and program details.

A school may operate more than one program.

### program_sites.csv
Links programs to schools, with beginning and ending
years. Allows programs to move, expand, or close.

### instructional_history.csv
Records the instructional-language allocation for
each entering cohort and grade.

For example, a school that changes from 50-50 to
90-10 must retain separate histories for students
who entered before and after the change.

Actual language allocations by grade are recorded
separately from advertised program labels.

### sources.csv
Tracks evidence supporting school identities,
program classifications, model histories, and dates.

## Research principles

1. School identity and program identity are distinct.

2. Instructional allocation is time-dependent and
   may differ by entering student cohort and grade.

3. Schoolwide outcomes must never be silently
   treated as dual-language participant outcomes.

4. Unverified model classifications remain unknown.
   Missing values must never be interpreted as zero.

5. Reported outcomes retain source, assessment,
   year, grade, subgroup, and reporting scope.

6. Changes in assessment standards are documented.

7. Historical source records are preserved, even
   when later corrections are made.

8. Student-level restricted data are not stored in
   this public-facing research structure.

## Research datasets

The national registry will support two complementary
analyses:

A. Matched-school comparisons among dual-language
schools using different instructional allocations.

B. Participant-specific analyses in states that
report outcomes for students enrolled in
dual-language programs.

Within-state comparisons will be preferred where
assessment systems or proficiency definitions differ.

## Current status

Registry structure established.
School records and historical model classifications
await migration and verification.
