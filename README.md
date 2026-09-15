# Virelion-CardiTrace

CardiTrace records computational provenance, artifact identity, lineage, execution context, integrity metadata, and reproducibility state for Virelion workflows.

## Architecture

- SHA-256 identities for payloads, files, models, datasets, reports, and configurations.
- Append-only hash-chained events and Merkle commitments.
- Execution fingerprints over code, environment, inputs, parameters, and seeds.
- Run/session records, resource telemetry, policy gates, redaction, replay comparison, and federation.
- Semantic entity/activity/agent/relation graph shaped for W3C PROV interoperability.
- Dataset manifests for external, local, and derived scientific datasets.
- Provenance cards and upstream/downstream impact analysis.
- Low-friction context-manager/decorator instrumentation.
- OpenLineage-shaped event export without requiring the OpenLineage SDK.
- Deterministic pipeline stage locks and transitive downstream invalidation.
- Local file content-hash verification during audits.
- Existing HeartTwin adapter and component handoff APIs.

## Quick start

```python
from cardi_trace import TraceRecorder, activity, record_result

trace = TraceRecorder("./trace", component="example")
with activity(trace, "example", "operation", parameters={"seed": 42}) as run:
    result = {"value": 42}
    record_result(trace, run.run_id, result)
```

Semantic projection and a compact provenance card:

```python
from cardi_trace import graph_from_recorder, provenance_card

graph = graph_from_recorder(trace)
card = provenance_card(graph, title="Example analysis", run_id=run.run_id)
```

Pipeline lock state:

```python
from cardi_trace import Pipeline, Stage, lock_pipeline

pipeline = Pipeline()
pipeline.add(Stage("prepare", "python prepare.py", outs=("prepared",)))
pipeline.add(Stage("train", "python train.py", deps=("prepared",), outs=("model",)))
lock_pipeline(pipeline, path="carditrace.lock.json")
```

## CLI

```bash
carditrace demo ./trace-demo
carditrace verify ./trace-demo
carditrace inspect ./trace-demo
carditrace bundle ./trace-demo/bundle.json
```

## Interoperability

CardiTrace's semantic model is deliberately close to W3C PROV concepts. It also provides an OpenLineage-shaped event export so traces can be mapped into systems using run/job/dataset lineage semantics. These exporters do not require external runtime dependencies.

## Validation

CI is configured for Python 3.10–3.13 and runs compilation plus the pytest suite. The repository also contains explicit tests for semantic provenance, instrumentation, pipeline locking, lineage export, and audit behavior.

## Design lineage

The implementation was informed by public patterns in Flowcept, RI-SE/dataprov, DVC, OpenLineage, and related scientific provenance systems. CardiTrace is not presented as a source-code fork of those projects. Source-level reuse of external code must be handled separately under the applicable upstream license.

## Limitations

Integrity hashes and Merkle commitments detect ordinary post-hoc modification but do not create an independent trust anchor against an attacker who controls the original data, runtime, repository, and verifier. Missing external files cannot be content-verified locally. Provenance documents computational history; it does not establish scientific validity or correctness of an analysis.

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See `LICENSE`.
