"""Reviewed Wisconsin structural sources."""
from .great_lakes import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'WI')
