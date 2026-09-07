# Virelion-CardiTrace

CardiTrace is a provenance and reproducibility library for recording computational runs, artifacts, lineage, execution fingerprints, and integrity metadata.

## What it contains

- SHA-256 identities for payloads, files, models, datasets, reports, and configurations.
- Hash-chained trace events.
- Execution fingerprints based on code, environment, inputs, parameters, and seeds.
- Run/session records.
- Content-addressed artifact storage.
- Artifact lineage and cycle checks.
- Schema-versioned trace bundles.
- Merkle-root integrity commitments.
- Trace envelopes for exchanging trace IDs, artifact references, and integrity commitments.
- Provenance policy gates and regression comparison.
- Replay planning and identity comparison without executing arbitrary code.
- Metadata redaction.
- Read-only lineage/query APIs and CLI tools.

## Installation

```bash
python -m pip install -e '.[test]'
```

## Usage

CLI:

```bash
carditrace demo ./trace-demo
carditrace verify ./trace-demo
carditrace inspect ./trace-demo
carditrace bundle ./trace-demo/bundle.json
```

Python:

```python
from cardi_trace import TraceRecorder

trace = TraceRecorder("./trace", component="example")
run = trace.start_run("example", "operation", parameters={"seed": 42})
# register and attach inputs/outputs, then finish the run
trace.finish_run(run.run_id)
```

## Inputs and outputs

**Inputs:** run metadata, component/operation identifiers, parameters, seeds, environment/code fingerprints, input/output artifacts, and optional provenance metadata.

**Outputs:** trace events, run/session records, artifact identities, lineage records, trace bundles/envelopes, integrity commitments, verification reports, and replay-comparison results.

## Validation

The test suite covers trace creation, identity/hash behavior, lineage checks, bundle handling, and verification behavior. Verification checks captured identities and integrity commitments without executing arbitrary code from a trace.

## Limitations

Hashing and Merkle commitments detect ordinary post-hoc changes but do not protect against an attacker who controls the original data, runtime, repository, and verification environment. Higher assurance requires independent trust anchors or signed release artifacts. Provenance records document computational history; they do not establish scientific validity.

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See `LICENSE`.
