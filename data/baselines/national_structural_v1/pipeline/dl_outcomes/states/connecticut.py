"""Reviewed Connecticut structural sources."""
from .mid_atlantic_ct import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'CT')
