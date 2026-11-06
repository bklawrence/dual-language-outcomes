"""Reviewed West Virginia structural sources."""
from .oh_ky_wv_va import migrate_reviewed_state


def migrate(build):
    migrate_reviewed_state(build, 'WV')
