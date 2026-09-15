from pathlib import Path

from cardi_trace import ArtifactKind, ArtifactRef, ProvenanceGraph, dataset_manifest, graph_from_recorder, provenance_card, impact_report
from cardi_trace import TraceRecorder


def test_provenance_graph_round_trip_semantics():
    g = ProvenanceGraph()
    g.entity("dataset:raw", source="GEO:GSE217494")
    g.activity("activity:qc", operation="qc")
    g.entity("dataset:qc", stage="qc")
    g.used("activity:qc", "dataset:raw")
    g.generated("dataset:qc", "activity:qc")
    g.derived("dataset:qc", "dataset:raw")
    assert "dataset:raw" in g.upstream("dataset:qc")
    assert "dataset:qc" in g.downstream("dataset:raw")
    assert g.to_dict()["prefix"]["prov"] == "http://www.w3.org/ns/prov#"
    assert len(g.digest) == 64


def test_dataset_manifest_is_deterministic():
    artifact = ArtifactRef.create("a" * 64, kind=ArtifactKind.DATASET, name="matrix.h5ad")
    a = dataset_manifest("GEO", [artifact], version="GSE217494", modality="scRNA-seq")
    b = dataset_manifest("GEO", [artifact], version="GSE217494", modality="scRNA-seq")
    assert a["dataset_id"] == b["dataset_id"]
    assert a["manifest_digest"] == b["manifest_digest"]


def test_existing_recorder_projects_into_semantic_graph(tmp_path: Path):
    recorder = TraceRecorder(tmp_path, actor="test", component="unit")
    run = recorder.start_run("unit", "analysis", parameters={"seed": 7})
    artifact = recorder.register_payload({"x": 1}, kind=ArtifactKind.DATASET)
    recorder.attach_input(run.run_id, artifact)
    recorder.finish_run(run.run_id)
    graph = graph_from_recorder(recorder)
    assert f"artifact:{artifact.artifact_id}" in graph.entities
    assert f"activity:{run.run_id}" in graph.activities
    card = provenance_card(graph, title="unit")
    assert card["graph_digest"] == graph.digest
    assert impact_report(graph, f"artifact:{artifact.artifact_id}")["entity_id"]
