# CardiTrace trace format 2.0

A bundle contains `schema_version` (`2.0`), ordered `events`, `runs`, `artifacts`, `lineage`, an export-time `audit`, a Merkle `commitment`, and `bundle_digest`. The bundle digest is SHA-256 of the canonical payload after removing `bundle_digest`. The loader recomputes the journal hashes, reconstructed snapshots, references, run fingerprints and Merkle root rather than trusting the embedded audit.

## Canonical identities

Artifact IDs are `sha256:<lowercase hex>`. Files use SHA-256 of raw bytes. Payloads and CAS JSON use the same UTF-8 canonical JSON: sorted string keys, compact separators, unescaped Unicode, recursive tuple/list and set normalization, enum values and `to_dict` objects. Non-finite floats and dictionary keys that collide after string normalization are rejected. Other legacy values use string conversion; portable scientific interchange should use JSON-compatible values.

Each event has a unique `event_id`, Unix timestamp, event type, actor, component, object payload, optional run ID, previous hash and event hash. Compute the event hash with `event_hash` set to the empty string. The first previous hash is null. Journal order is significant. Lifecycle event types are reserved for recorder methods.

## Durable local ledger

`events.jsonl` is canonical. `runs.json`, `artifacts.json`, and `lineage.json` are derived snapshots. Writes take a cooperative process/thread lock, reload state, verify integrity, append and fsync the journal, then atomically replace/fsync snapshots. Readers may retain an older in-memory view; reopen a recorder for a fresh view. Returned records are detached copies.

A failure after journal append can leave snapshots incomplete. Verification then fails, and subsequent writes refuse to proceed. Explicit recovery rebuilds snapshots only after checking journal hashes and references:

```bash
carditrace recover ./trace
# Use only when malformed snapshot JSON must be replaced:
carditrace recover ./trace --overwrite
```

`--overwrite` never bypasses journal validation. Partial, missing or modified journal entries are not silently repaired. Multi-file snapshots are not a database transaction, and the lock is a local cooperative lock, not a distributed/network-filesystem guarantee.

## Runs and artifacts

Run statuses are `running`, `succeeded`, `failed`, and `cancelled`. Terminal runs require a finish timestamp. Parent runs and attached artifacts must exist. Execution identity binds code, recorded environment, input identities, parameters and seeds. Finishing twice, invalid statuses and overwriting reserved execution metadata are rejected. Metadata updates remain journaled. One current artifact descriptor exists per content digest; registering the same content again replaces its descriptor, with both registrations retained in the journal.

Local file hashes are checked when files are accessible. Unavailable local references are warnings by default; `carditrace verify ./trace --strict-files` makes them errors. Payload registration captures an identity, not the payload bytes; use `ArtifactStore` if byte retention is required.

## Store and cache

CAS reads verify content hashes. Open handles are read-only. Writes reject corrupted existing blobs. GC retains directory-manifest descendants and coordinates with store writes. The supplied keep set still determines which application artifacts remain live. GC may materialize kept JSON/manifest blobs in memory.

Result caches contain a cache key, value and value digest. Corrupt or unverified legacy entries fail closed; remove legacy entries and recompute them. Cache and CAS digests are lowercase SHA-256 values, not arbitrary paths.

## Interchange boundaries

OpenLineage export uses the recorded start snapshot, rather than retroactively presenting final outputs as start-time observations. Import preserves lifecycle, metrics, tags and dataset descriptors and handles repeated START/terminal delivery. Dataset descriptors are marked `content_verified=false`; importing a descriptor does not verify upstream source bytes. Import timestamps describe local ingestion, while terminal upstream event time is retained in metadata.

Federation verifies the underlying trace, artifact set and optional HMAC. HMAC requires a shared secret and is not independent third-party attestation. Hash commitments need an external anchor to detect an adversary rewriting an entire journal and its snapshots or deleting an otherwise valid terminal suffix.
