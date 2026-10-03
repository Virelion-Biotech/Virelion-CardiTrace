# CardiTrace architecture v0.2

CardiTrace is a four-plane provenance system.

## Identity plane

Every artifact receives a content identity. Structured payloads use canonical JSON + SHA-256; files use streaming SHA-256. Every run additionally receives an execution fingerprint over code identity, environment identity, input identities, parameters, and deterministic seeds.

## Evidence plane

The recorder maintains an append-only event ledger, logical run registry, artifact registry, and first-class lineage graph. Event records hash-chain to the previous event. Metadata is redacted at the boundary for common credential-like keys.

## Integrity plane

Verification covers event chain correctness, event digests, artifact references, terminal-run completeness, lineage acyclicity, execution-fingerprint presence, and a Merkle root over the event chain. Bundle digests protect the complete exported evidence object. The Merkle root can be anchored outside CardiTrace.

## Interoperability plane

Versioned schema envelopes provide stable JSON interchange. Federation envelopes allow separate Virelion repositories to exchange trace IDs, artifact IDs, and Merkle commitments without sharing a database. OpenTelemetry-shaped spans can be exported without making OpenTelemetry a runtime dependency.

## Trust model

CardiTrace is an evidence and verification layer, not a trusted execution sandbox. Replay is represented as a plan and identity comparison rather than arbitrary code execution. A privileged attacker who controls all source data, trace storage, and the verifier can rewrite evidence; external signing or independent anchoring is required for stronger non-repudiation.

## Typical lifecycle

```text
input artifact
    │
    ▼
start_run ──► execution fingerprint
    │
    ├── attach input artifacts
    ├── application computation
    ├── register output artifacts
    ├── write lineage edges
    ▼
finish_run
    │
    ├── refresh execution fingerprint
    ├── append final event
    ▼
audit ──► Merkle root ──► export bundle ──► federation / archive / CI
```
