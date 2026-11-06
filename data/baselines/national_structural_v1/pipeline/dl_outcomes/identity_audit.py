"""Keep historical identity checks meaningful when a reviewed state expands."""
import hashlib
import json

EXPANSION = 'config/research_migrations/great_lakes_2026_11_05.json'


def fingerprint(ids):
    return hashlib.sha256(json.dumps(sorted(ids), separators=(',', ':')).encode()).hexdigest()


def preserved_identity_fingerprint(root, table, state, current_ids, expected):
    """Check the original set, with additions checked by the new batch audit.

    An expansion can narrow an old comparison only when its saved original IDs
    reproduce that old audit's independently frozen checksum. Missing/replaced
    original IDs still fail. Other states retain exact-set checks.
    """
    path = root / EXPANSION
    if path.exists():
        config = json.loads(path.read_text())
        original = config.get('expanded_state_original_ids', {}).get(table, {}).get(state)
        if original is not None and fingerprint(original) == expected:
            return fingerprint(set(current_ids) & set(original))
    return fingerprint(current_ids)
