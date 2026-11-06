"""California reviewed structural research and historical screening leads."""
from .five_state import migrate_state


def migrate(b):
    migrate_state(b, 'CA')
