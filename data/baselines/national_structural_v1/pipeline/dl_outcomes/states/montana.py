"""Montana reviewed structural research with separate immersion/funding status."""
from .five_state import migrate_state


def migrate(b):
    migrate_state(b, 'MT')
