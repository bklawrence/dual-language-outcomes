"""Reviewed Nebraska structural sources."""
from .western_plains import migrate_state


def migrate(build):
    migrate_state(build, 'NE')
