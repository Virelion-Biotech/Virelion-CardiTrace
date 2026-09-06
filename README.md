# Virelion-CardiTrace

CardiTrace is a provenance and reproducibility library for recording computational runs, artifacts, lineage, execution fingerprints, and integrity metadata across Virelion repositories.

## Scope

- SHA-256 identities for payloads, files, models, datasets, reports, and configurations;
- hash-chained trace events;
- execution fingerprints based on code, environment, inputs, parameters, and seeds;
- run/session records;
- content-addressed artifact storage;
- artifact lineage and cycle checks;
- schema-versioned trace bundles;
- Merkle-root integrity commitments;
- cross-repository trace envelopes;
- provenance policy gates and regression comparison;
- replay planning and identity comparison without executing arbitrary code;
- metadata redaction;
- read-only lineage/query APIs and CLI tools.

## Identity model

```text
artifact identity
      ↓
execution identity
      ↓
workflow lineage
      ↓
evidence/integrity identity
```

A replay comparison checks captured identities; CardiTrace does not execute arbitrary code from a trace.

## Installation

```bash
python -m pip install -e '.[test]'
```

## CLI

```bash
carditrace demo ./trace-demo
carditrace verify ./trace-demo
carditrace inspect ./trace-demo
carditrace bundle ./trace-demo/bundle.json
```

## Python API

```python
from cardi_trace import TraceRecorder

trace = TraceRecorder("./trace", component="CardiEval")
run = trace.start_run("CardiEval", "evaluate", parameters={"seed": 42})
# register and attach inputs/outputs, then finish the run
trace.finish_run(run.run_id)
```

## Federation

Repositories can exchange trace envelopes containing trace IDs, artifact references, and integrity commitments. Consumers can verify the envelope against their local trace without importing another repository's implementation.

## Security and integrity limitations

Hashing and Merkle commitments detect ordinary post-hoc changes to recorded artifacts. They do not protect against an attacker who controls the original data, runtime, repository, and verification environment. Higher assurance requires independent trust anchors or signed release artifacts.

CardiTrace records computational provenance. It does not generate biological construction or experimental instructions.

## Integration

CardiTrace can record runs from CardiAgent, CardiVex, CardiAtlas, CardiBench, CardiEval, CardiLearn, CardiSim, and HeartTwin without making those repositories runtime dependencies.

## Testing

```bash
pytest
```

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See `LICENSE`.

## Citation

Cite the repository release and the trace schema/version used for reproducibility records.
