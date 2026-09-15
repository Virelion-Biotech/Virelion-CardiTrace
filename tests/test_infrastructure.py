from pathlib import Path
from cardi_trace import ArtifactKind, SQLiteTraceIndex, TraceRecorder, add_column_lineage, ingest_openlineage_event, recover_from_events, reverse_column_lineage, verify_envelope

def test_recovery_rebuilds_state(tmp_path):
    root=tmp_path/"trace"; r=TraceRecorder(root)
    run=r.start_run("model","fit")
    inp=r.register_payload({"x":1},kind=ArtifactKind.DATASET); r.attach_input(run.run_id,inp)
    out=r.register_payload({"y":2},kind=ArtifactKind.MODEL); r.attach_output(run.run_id,out)
    add_column_lineage(r,inp.artifact_id,out.artifact_id,{"y":["x"]},run_id=run.run_id)
    r.log_metric(run.run_id,"score",0.91); r.finish_run(run.run_id)
    (root/"runs.json").unlink(); (root/"artifacts.json").unlink(); (root/"lineage.json").unlink()
    recovered=recover_from_events(root)
    assert recovered.runs[0].run_id==run.run_id
    assert recovered.runs[0].metrics["score"]==0.91
    assert recovered.lineage[0].metadata["column_lineage"]=={"y":["x"]}

def test_sqlite_index_and_column_lineage(tmp_path):
    r=TraceRecorder(tmp_path/"trace")
    run=r.start_run("model","fit")
    a=r.register_payload({"x":1}); b=r.register_payload({"y":2}); r.attach_input(run.run_id,a); r.attach_output(run.run_id,b)
    add_column_lineage(r,a.artifact_id,b.artifact_id,{"y":"x"},run_id=run.run_id)
    r.finish_run(run.run_id)
    index=SQLiteTraceIndex(tmp_path/"index.db").rebuild(r)
    assert len(index.runs(component="model"))==1
    assert b.artifact_id in index.downstream(a.artifact_id)
    assert reverse_column_lineage({"y":"x"})=={"x":["y"]}
    index.close()

def test_openlineage_import(tmp_path):
    source=TraceRecorder(tmp_path/"source")
    run=source.start_run("external","job",parameters={"x":1})
    source.log_metric(run.run_id,"acc",0.8); source.finish_run(run.run_id)
    from cardi_trace import events_from_recorder
    target=TraceRecorder(tmp_path/"target")
    events=events_from_recorder(source)
    imported=ingest_openlineage_event(target,events[0],source="test")
    assert imported.tags["external_run_id"]==run.run_id
    ingest_openlineage_event(target,events[1],source="test")
    assert str(target.runs[0].status)=="succeeded"
