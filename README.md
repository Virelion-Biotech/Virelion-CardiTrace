# Virelion-CardiTrace

**High-assurance provenance, lineage, reproducibility, audit, federation, and telemetry infrastructure for Virelion's cardiac AI ecosystem.**

CardiTrace is the evidence layer across CardiAgent → CardiVex → CardiBench → CardiEval → CardiAtlas → CardiLearn → CardiSim. It is intentionally implementation-agnostic: sibling repositories emit structured trace events and artifact identities without importing one another.

## Why v0.2 is substantially stronger

CardiTrace is no longer just an append-only logger. Each logical computation now receives an **execution fingerprint** derived from code identity, environment, inputs, parameters, and deterministic seeds. Artifacts remain content-addressed, lineage is persisted as a first-class graph, metadata is automatically redacted at the trace boundary, and bundles carry a Merkle commitment that can be anchored outside the repository.

The platform now supports:

- SHA-256 identities for files, payloads, configurations, models, datasets, reports, and code snapshots
- append-only hash-chained events
- execution fingerprints for computational identity and replay comparison
- explicit run/session records with inputs, outputs, code, environment, seeds, and status
- persistent artifact lineage with cycle detection during audit
- local content-addressed object storage
- schema-versioned portable bundles with integrity-checked loading
- Merkle roots for efficient external integrity anchoring
- federated cross-repository trace envelopes
- policy gates for CI/release provenance requirements
- trace diffing and regression detection
- replay planning and identity validation without executing arbitrary code
- sensitive-metadata redaction
- OpenTelemetry-shaped span export without forcing a telemetry dependency
- read-only query APIs for lineage, runs, artifacts, and fingerprints
- CLI inspection and bundle-verification commands

## Architecture

```text
                              CardiTrace
                                  │
        ┌─────────────────────────┼──────────────────────────┐
        │                         │                          │
   Identity plane            Evidence plane             Integrity plane
        │                         │                          │
 fingerprints              event ledger                Merkle root
 artifact hashes            run registry                audit engine
 code/env/seed IDs          artifact registry            policy gates
        │                         │                          │
        └─────────────────────────┼──────────────────────────┘
                                  │
                           lineage / federation
                                  │
          ┌───────────────┬───────┴────────┬───────────────┐
          ▼               ▼                ▼               ▼
      CardiAgent       CardiVex        CardiLearn       CardiEval
          │               │                │               │
          └───────────────┴────────────────┴───────────────┘
                                  │
                         reproducible evidence
                                  │
                    archive / CI / external anchor
```

## Quick start

```bash
python -m pip install -e '.[test]'
carditrace demo ./trace-demo
carditrace verify ./trace-demo
carditrace inspect ./trace-demo
carditrace bundle ./trace-demo/bundle.json
```

Python:

```python
from cardi_trace import TraceRecorder, TracePolicy, TraceQuery

trace = TraceRecorder("./trace", component="CardiEval")
run = trace.start_run(
    "CardiEval",
    "evaluate",
    parameters={"split": "test", "seed": 42},
    seeds={"numpy": 42, "python": 42},
)

raw = trace.register_payload({"benchmark": "CardiBench", "n": 256}, role="input")
trace.attach_input(run.run_id, raw)

result = trace.register_payload({"accuracy": 0.91}, role="output")
trace.attach_output(run.run_id, result)
trace.add_lineage(raw.artifact_id, result.artifact_id, run_id=run.run_id)
trace.finish_run(run.run_id)

TracePolicy(require_outputs_for_success=True).assert_compliant(trace)
print(TraceQuery(trace).execution_fingerprints())
trace.export_bundle("bundle.json")
```

## Strong reproducibility model

A trace can distinguish four levels of identity:

1. **Artifact identity** — the bytes or canonical payload.
2. **Execution identity** — code + environment + inputs + parameters + seeds.
3. **Workflow identity** — the lineage graph linking transformations.
4. **Evidence identity** — the event-chain and Merkle commitment covering what was recorded.

A replay comparison is therefore explicit. CardiTrace produces a replay plan and validates a newly captured run against the original identity; it does not pretend that arbitrary code can safely be executed from an untrusted trace.

## Cross-repository federation

A repository can create an envelope containing a trace ID, artifact references, and Merkle root. Another Virelion repository can independently verify the envelope against its local trace. This allows CardiAgent, CardiVex, CardiEval, and the rest of the ecosystem to preserve autonomy while still producing a joinable evidence graph.

## Integrity and threat model

CardiTrace detects ordinary post-hoc tampering through event hashes, artifact hashes, lineage verification, bundle digests, and Merkle commitments. It is not a magical anti-adversary system: an attacker with control of the original data, repository, runtime, and verification software can replace all of them. Higher assurance comes from independently anchoring Merkle or bundle digests in signed releases, immutable object storage, or another trust domain.

## Scientific boundary

CardiTrace records scientific and machine-learning provenance. It does not generate operational wet-lab protocols, pathogen sequences, culturing conditions, doses, or other biological construction instructions.

## Compatibility

- Python: 3.10+
- Runtime dependencies: Python standard library only
- Test dependency: `pytest`
- Canonical integration branch: `main`

## Package layout

```text
src/cardi_trace/
  models.py         immutable data model
  recorder.py       durable provenance capture + execution fingerprints
  hashing.py        canonicalization + SHA-256 identity
  fingerprint.py    code/environment/execution identity
  lineage.py        graph algorithms
  audit.py          multi-layer verification
  export.py         schema-versioned bundles
  schema.py         trace schema + migration helpers
  merkle.py         external integrity commitments
  federation.py     cross-repository envelopes
  policy.py         provenance policy gates
  diff.py           regression comparison
  replay.py         replay planning + validation
  redaction.py      sensitive metadata filtering
  telemetry.py      OpenTelemetry-shaped export
  query.py          read-only query engine
  store.py          content-addressed artifact store
  integration.py    Virelion adapter helpers
  context.py        context manager + decorator API
  cli.py             command-line interface
```

**Current release: `0.2.0`.**
