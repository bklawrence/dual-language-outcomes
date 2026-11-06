"""Reviewed Vermont structural sources."""
from .new_england import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'VT')
