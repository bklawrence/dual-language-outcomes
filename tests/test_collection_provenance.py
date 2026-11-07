"""Archived provenance must retain exact bytes without relaxing integrity."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from dl_outcomes.collection_provenance import ARCHIVES, pinned_dependency


def fingerprint(value):
    return hashlib.sha256(value).hexdigest()


class PinnedCollectionProvenanceTests(unittest.TestCase):
    def test_old_dependency_can_survive_a_new_live_structural_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); collection = root/'collection'; collection.mkdir()
            manifest = b'{"immutable_collection":"original"}'
            (collection/'manifest.json').write_bytes(manifest)
            original = b'original structural input\n'; expected = fingerprint(original)
            live = root/'claims.csv'; live.write_bytes(original + b'new delivery observation\n')
            compressed = gzip.compress(original, mtime=0)
            saved = root/'claims.csv.gz'; saved.write_bytes(compressed)
            receipt = root/ARCHIVES; receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps(dict(collection_manifest_sha256=fingerprint(manifest), dependencies=[
                dict(kind='input', original_path='claims.csv', original_sha256=expected,
                     archive_path='claims.csv.gz', archive_sha256=fingerprint(compressed), compression='gzip')
            ])))
            self.assertEqual(pinned_dependency(root,collection,'input','claims.csv',expected),saved)
            # An archive cannot be repurposed for another collection, role,
            # original path or expected content hash.
            for kind, path, checksum in [('pipeline','claims.csv',expected),
                                         ('input','other.csv',expected),
                                         ('input','claims.csv',fingerprint(b'different'))]:
                with self.assertRaises(ValueError):
                    pinned_dependency(root,collection,kind,path,checksum)
            (collection/'manifest.json').write_bytes(b'changed collection')
            with self.assertRaises(ValueError):
                pinned_dependency(root,collection,'input','claims.csv',expected)
            (collection/'manifest.json').write_bytes(manifest)
            saved.write_bytes(gzip.compress(b'different old evidence',mtime=0))
            with self.assertRaises(ValueError):
                pinned_dependency(root,collection,'input','claims.csv',expected)
            # Even an updated compressed-byte receipt cannot substitute
            # different decompressed evidence for the original pinned hash.
            changed = json.loads(receipt.read_text())
            changed['dependencies'][0]['archive_sha256'] = fingerprint(saved.read_bytes())
            receipt.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                pinned_dependency(root,collection,'input','claims.csv',expected)


if __name__ == '__main__':
    unittest.main()
