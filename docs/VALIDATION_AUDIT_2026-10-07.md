# CardiTrace 0.4.1 validation and repair audit

Scope: all source modules, public APIs, CLI, HeartTwin command adapter, interchange, persistence, CAS/cache, packaging and CI. Baseline: main commit `f09f5872a4f99fe8819f03f299194c508d4b6bef`. This is software integrity/reproducibility validation, not validation of cardiac physiology or upstream scientific conclusions.

## Reproduced defects and repairs

The original 32 tests passed. The first targeted regression panel produced 17 failures, including three non-finite-metric cases. Repairs and subsequent checks cover:

| Area | Defect | Repair/evidence |
|---|---|---|
| Ledger integrity | Snapshot modification escaped audit | Reconstruct and compare state against hash-checked journal |
| Recovery | Modified journal was accepted; attached-input fingerprint was stale | Validate before any overwrite; refresh fingerprints during replay |
| Persistence | Two recorder instances could lose runs and fork the chain | Reload and serialize writes under thread/process locking |
| Crash handling | Snapshot writes preceded canonical events and were non-atomic | Journal-first fsync and atomic snapshot replacement; injected interruption test |
| Mutable state | Returned nested dictionaries could alter internal records | Detached deep copies at boundaries |
| Lifecycle | Invalid/repeated finish and reserved metadata/event writes | Validate statuses, transitions, identities and reserved events |
| Numeric capture | NaN/Infinity entered metrics and hashes | Reject non-finite values |
| Redaction | Sensitive tag values leaked into snapshots and events | Apply key-based redaction before capture |
| Identity | Recorded environment was not bound; staged/untracked code was missed | Bind captured environment and hash dirty tracked/untracked code |
| Pipeline locks | Dependency filename changes and removed producers escaped invalidation | Bind declarations and propagate full dependency changes; reject duplicate outputs |
| Cache | Traversal keys, corrupt values and cached null mishandled | Strict digest keys, atomic checked envelopes, null cache hits |
| CAS | Unicode/set JSON identity differed; corrupt blobs were returned | Share canonical JSON and verify stored bytes |
| CAS GC | Retained directories lost their child files | Traverse manifest references under store write lock |
| Comparison | Changed artifact descriptors could still report identical | Compare full trace digests |
| Provenance | Input-to-output traversal reversed; specialization dropped; actor changed on reload | Correct dataflow and exports; recover actors from journal |
| Interchange | Outer bundle digest could hide invalid journal | Independently verify inner journal/snapshots/commitment |
| Federation/replay | Incomplete artifact sets, invalid traces, environment/output changes missed | Check trace validity, exact sets and replay identities |
| OpenLineage | Repeated delivery duplicated runs; metrics/descriptors lost; START showed future outputs | Idempotent lifecycle import, retained metrics/descriptors and recorded start snapshots |
| CLI | Missing path could appear valid and create a directory; malformed input raised unstructured exceptions | Fail missing verification without creation; structured errors; explicit recovery and strict-file mode |
| Packaging | Facet schemas absent from wheel; documentation stale; license text abbreviated | Package facets, include docs/scripts in sdist, update format docs and include complete AGPL text |

## Validation commands

```bash
python -m pip install -e '.[test]' build ruff coverage
python -m compileall -q src tests scripts
python -m ruff check src tests scripts --select E9,F63,F7,F82
python -m pytest -q
python -m coverage run --source=cardi_trace -m pytest -q
python -m coverage report -m
python -m build --wheel --sdist
# Install the built wheel in a clean environment, then:
python scripts/package_smoke.py --installed
```

The repaired suite contains 72 tests. CPU-only local execution on Linux/Python 3.12 passed. Regression scenarios include concurrent spawn processes and threads sharing a recorder, interrupted snapshot writes, malformed snapshots, modified journals, rehashed corrupt bundles, strict missing-file checks, descriptor-aware GC, cache corruption, external lifecycle duplication, and staged/untracked code changes. Existing HeartTwin fingerprint fixtures pass. The package smoke harness exercises both command adapters, successful exports and canonical-state tamper rejection. CI runs Python 3.10–3.13 on Ubuntu and Windows and also installs/exercises the built wheel. CI outcomes must be checked for the actual pushed commit; configuration alone is not a pass.

## Limits of the evidence

This audit establishes tested behavior, not perfection or absence of every possible defect. Locks protect cooperating local writers; shared network/distributed filesystems and malicious direct writes require separate infrastructure testing. No power-loss/hardware-fault certification was performed. Recovery refuses damaged canonical journals rather than inventing omitted history. Key-based redaction does not scan free-text exceptions or arbitrary user payload contents for secrets. Payload identity alone does not retain raw bytes. Full trace loading/auditing rewrites snapshots and scales with ledger size; no high-volume performance guarantee is claimed. Full stack remote-service deployment was not independently revalidated here. Scientific truth and independent collection authenticity require external evidence and trusted anchors.
