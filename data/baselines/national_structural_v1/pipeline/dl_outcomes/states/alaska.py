"""Reviewed Alaska structural sources."""
from .northern_central import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'AK')
