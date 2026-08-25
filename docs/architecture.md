# CardiTrace architecture

## 1. Identity layer

Every material object receives a SHA-256 identity. Structured payloads are canonicalized recursively before hashing; files are streamed through SHA-256. The identifier is therefore portable across machines and storage backends.

## 2. Provenance ledger

`TraceRecorder` writes one JSON object per event to `events.jsonl`. Each event contains the previous event hash and its own digest. This creates a tamper-evident sequence:

```text
E0 -> hash(E0)
      ↓
E1(previous=hash(E0)) -> hash(E1)
      ↓
E2(previous=hash(E1)) -> hash(E2)
```

The ledger is append-only at the API level. Verification recomputes each digest and checks the chain.

## 3. Run model

A run identifies one logical computation. It explicitly carries component, operation, parameters, environment, code identity, parent run, inputs, outputs, timestamps, status, and metadata. This separates *what was run* from the event stream that records *what happened*.

## 4. Artifact registry

Artifacts are references rather than copied scientific datasets. CardiTrace records digest, type, media type, size, URI, role, and metadata. `ArtifactStore` provides optional local content-addressed retention.

## 5. Lineage

`LineageGraph` models transformations between artifact identities. Cycles are rejected and topological ordering is available. This supports questions such as: “Which raw dataset contributed to this evaluation?” and “Which reports descend from this model checkpoint?”

## 6. Evidence bundles

A bundle contains the event ledger, run records, artifact registry, and an audit result. It can be archived independently of the working directory. JSONL is available when streaming event ingestion is preferred.

## 7. Integration boundary

The integration helpers intentionally accept dictionaries rather than importing CardiAgent, CardiVex, CardiEval, or other sibling packages. This avoids a dependency cycle and allows each repository to evolve independently. Cross-repository handoffs are traced as content-addressed payloads.

## Threat model

CardiTrace detects accidental or ordinary post-hoc modification of trace files through hash verification. It does **not** provide cryptographic non-repudiation against a privileged attacker who can rewrite both the ledger and verification code. For higher assurance, publish bundle digests to an external immutable registry, signed release, or separate archival system.

## Reproducibility

A trace is reproducible when the same artifact identities, parameters, code identity, environment constraints, and deterministic seeds can be reconstructed. CardiTrace records the evidence; it does not pretend that a hash alone recreates unavailable external data.
