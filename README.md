# Virelion-CardiTrace

**An append-only provenance, lineage, reproducibility, and audit layer for Virelion's cardiac AI ecosystem.**

CardiTrace records *what happened, when, with which inputs, using which code/configuration, and what artifacts were produced*. It is designed to sit across CardiAgent → CardiVex → CardiBench → CardiEval → CardiAtlas → CardiLearn → CardiSim without becoming coupled to any one implementation.

## What it provides

- deterministic SHA-256 identities for files, payloads, configurations, and code snapshots
- append-only event records with hash chaining
- run/session records with explicit inputs, outputs, parameters, environment, and status
- artifact registry with content-addressed storage metadata
- typed lineage graph connecting datasets, transformations, models, predictions, evaluations, and reports
- verification of event chains, artifact hashes, lineage integrity, and manifest reproducibility
- portable JSON/JSONL trace bundles suitable for archival and external review
- a small filesystem-backed artifact store with no database requirement
- adapter helpers for upstream/downstream Virelion components
- CLI commands for hashing, recording, exporting, and verification

## Design principle

CardiTrace is an **evidence layer**, not a logging layer. A trace entry should be sufficient to reconstruct the identity of the object or computation it refers to, while keeping the actual scientific payload optional. Hashes are preferred over copied data; explicit metadata is preferred over implicit state.

```text
                         CardiTrace
                             │
     ┌───────────────────────┼─────────────────────────┐
     │                       │                         │
 provenance ledger       artifact registry       lineage graph
     │                       │                         │
     └───────────────────────┼─────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   CardiAgent            CardiVex             CardiEval
        │                    │                    │
        └─────────────── traced workflow ────────┘
                             │
                reproducible evidence bundle
```

## Quick start

```bash
python -m pip install -e .
carditrace hash README.md
carditrace demo ./trace-demo
carditrace verify ./trace-demo
```

Python API:

```python
from cardi_trace import TraceRecorder, TraceStatus

recorder = TraceRecorder("./trace")
run = recorder.start_run(
    component="CardiEval",
    operation="evaluate",
    parameters={"split": "test", "seed": 42},
)
input_ref = recorder.register_payload({"benchmark": "demo", "n": 32}, role="input")
recorder.attach_input(run.run_id, input_ref)
output_ref = recorder.register_payload({"accuracy": 0.91}, role="output")
recorder.attach_output(run.run_id, output_ref)
recorder.finish_run(run.run_id, status=TraceStatus.SUCCEEDED)
recorder.export_bundle("bundle.json")
```

## Repository layout

```text
src/cardi_trace/
  models.py        immutable public data model
  hashing.py       canonicalization and SHA-256 identity
  recorder.py      append-only provenance recorder
  lineage.py       directed artifact lineage graph
  manifest.py      reproducibility manifests
  audit.py         verification and audit reports
  store.py         filesystem content-addressed store
  export.py        portable trace bundle formats
  integration.py   Virelion component adapters
  cli.py           command-line interface
  version.py       package version

tests/             unit/integration tests
docs/              architecture and format specification
examples/          complete local workflow example
```

## Scientific boundary

CardiTrace can record arbitrary metadata but does not generate operational wet-lab protocols, pathogen sequences, culturing conditions, or other instructions for biological construction. It is a provenance system.

## Status

The `main` branch is the canonical integration branch. The package is intentionally dependency-light: the core runtime uses Python's standard library so trace capture remains usable inside isolated scientific pipelines.
