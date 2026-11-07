"""Verify exact archived dependencies of an immutable assessment collection."""
import gzip
import hashlib
import json

from .io import digest

ARCHIVES = 'data/provenance/edc_v3_1_2022_2025/archived_dependencies.json'


def pinned_dependency(root, collection, kind, relative, expected):
    """Return a hash-verified dependency, allowing only an explicit old receipt.

    Archives preserve the original collection's input/code bytes. They do not
    authorize new live evidence or transforms as replacements for those bytes.
    Compressed archives are checked against both stored and uncompressed hashes.
    """
    live = root / relative
    if live.is_file() and digest(live) == expected:
        return live
    receipt = root / ARCHIVES
    if receipt.is_file():
        archive = json.loads(receipt.read_text())
        manifest = collection / 'manifest.json'
        if digest(manifest) == archive['collection_manifest_sha256']:
            matches = [r for r in archive['dependencies']
                       if (r['kind'], r['original_path'], r['original_sha256']) == (kind, relative, expected)]
            if len(matches) == 1:
                row = matches[0]
                path = root / row['archive_path']
                if path.is_file() and digest(path) == row['archive_sha256']:
                    opener = gzip.open if row['compression'] == 'gzip' else open
                    fingerprint = hashlib.sha256()
                    with opener(path, 'rb') as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                            fingerprint.update(chunk)
                    if fingerprint.hexdigest() == expected:
                        return path
    raise ValueError('EDC pinned ' + kind + ' dependency changed or archive is unverified: ' + relative)
