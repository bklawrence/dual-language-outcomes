# Original EDC collection dependencies

The original EDC collection pins the pre-cleanup canonical evidence-claims CSV
and collection code by hash. Live structural enrichment changes the canonical
file and requires a collection-registration fix, so these exact original bytes
are preserved here. `archived_dependencies.json` binds each archive to its
original path, role, SHA-256 and the unchanged collection manifest's SHA-256.
Gzip archives must pass both stored-byte and decompressed-byte hash checks.

The original assessment collection manifest, targets, identity matches, native
extracts, normalized result cells, partition receipts and summary files remain
unchanged. Validation now checks the archived dependencies when the live paths
have advanced. The current build manifest tracks both the current pipeline and
these archived dependencies. This does not treat new structural evidence as an
input used to produce the older collection.
