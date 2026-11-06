"""Reviewed New York structural sources."""
from .mid_atlantic_ct import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'NY')
