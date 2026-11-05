"""Reviewed Arkansas structural sources."""
from .south_central import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'AR')
