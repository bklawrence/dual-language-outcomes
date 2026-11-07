"""Reviewed South Carolina structural sources."""
from .southeast import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'SC')
