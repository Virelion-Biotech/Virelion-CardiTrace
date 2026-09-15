# Virelion-CardiTrace

CardiTrace is a high-assurance biomedical provenance and reproducibility library for Virelion cardiac AI workflows.

## Architecture

CardiTrace combines its original append-only, content-addressed ledger with interoperable provenance concepts drawn from mature open-source provenance systems. The implementation remains dependency-free.

- SHA-256 identities for payloads, files, models, datasets, reports, and configurations.
- Hash-chained trace events and Merkle commitments.
- Execution fingerprints over code, environment, inputs, parameters, and seeds.
- Run/session records, telemetry, policy gates, redaction, replay comparison, and federation.
- Semantic entity/activity/agent/relation graph compatible in shape with W3C PROV.
- Scientific dataset manifests for sources such as GEO, SRA, PhysioNet, local data, and derived datasets.
- Provenance cards for compact model/report registry metadata.
- Upstream/downstream impact analysis for change propagation.
- Projection of the existing CardiTrace recorder directly into the semantic graph, preserving legacy traces.
- Existing HeartTwin adapter and component handoff APIs remain part of the stack.

## Usage

```python
from cardi_trace import TraceRecorder, graph_from_recorder, provenance_card

trace = TraceRecorder("./trace", component="example")
run = trace.start_run("example", "operation", parameters={"seed": 42})
# register and attach inputs/outputs
trace.finish_run(run.run_id)

graph = graph_from_recorder(trace)
card = provenance_card(graph, title="Example analysis", run_id=run.run_id)
```

## CLI

```bash
carditrace demo ./trace-demo
carditrace verify ./trace-demo
carditrace inspect ./trace-demo
carditrace bundle ./trace-demo/bundle.json
```

## Validation

The test suite covers the legacy trace system plus semantic provenance graph construction, deterministic dataset manifests, ledger-to-PROV projection, provenance cards, and impact traversal.

## Design lineage

CardiTrace incorporates architectural lessons from Flowcept, RI-SE/dataprov, DVC, and scientific data-management systems. The current implementation is independent rather than a source-code fork. See `THIRD_PARTY_NOTICES.md` for attribution and the rules governing future source-level reuse.

## Limitations

Integrity hashes detect ordinary post-hoc changes but cannot establish trust against an attacker controlling the source, runtime, repository, and verifier. Provenance records computational history; they do not establish scientific validity.

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). See `LICENSE`.
