from cardi_trace import ArtifactKind, Pipeline, Stage, TraceRecorder, activity, changed_stages, export_openlineage, lock_pipeline, record_result

def test_activity_failure_and_output(tmp_path):
    trace = TraceRecorder(tmp_path / "trace", actor="test", component="test")
    with activity(trace, "unit", "work") as run:
        record_result(trace, run.run_id, {"answer": 42})
    assert trace.runs[0].status == "succeeded"
    assert len(trace.runs[0].output_artifacts) == 1

def test_pipeline_lock_and_cycle_detection(tmp_path):
    p = Pipeline()
    p.add(Stage("prepare", "prepare", outs=("prepared",)))
    p.add(Stage("train", "train", deps=("prepared",), outs=("model",)))
    lock = lock_pipeline(p, path=tmp_path / "trace.lock.json")
    assert lock["order"] == ["prepare", "train"]
    p2 = Pipeline()
    p2.add(Stage("a", "a", deps=("b",), outs=("a",)))
    p2.add(Stage("b", "b", deps=("a",), outs=("b",)))
    try:
        p2.topological_order()
        assert False, "expected cycle error"
    except ValueError as exc:
        assert "cycle" in str(exc).lower()

def test_openlineage_export(tmp_path):
    trace = TraceRecorder(tmp_path / "trace")
    run = trace.start_run("unit", "op")
    ref = trace.register_payload({"x": 1}, kind=ArtifactKind.DATASET)
    trace.attach_output(run.run_id, ref)
    trace.finish_run(run.run_id)
    path = export_openlineage(trace, tmp_path / "events.jsonl")
    text = path.read_text()
    assert '"eventType":"COMPLETE"' in text
    assert run.run_id in text

def test_changed_stages_propagates_downstream():
    old = {"stages": {"a": {"digest": "1"}, "b": {"digest": "2", "deps": ["a"]}, "c": {"digest": "3", "deps": ["b"]}}}
    new = {"stages": {"a": {"digest": "9"}, "b": {"digest": "2", "deps": ["a"]}, "c": {"digest": "3", "deps": ["b"]}}}
    assert changed_stages(old, new) == ["a", "b"]
