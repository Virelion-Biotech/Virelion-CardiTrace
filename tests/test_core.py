from pathlib import Path
from cardi_trace import TraceRecorder, TraceStatus, verify_recorder, LineageGraph
from cardi_trace.hashing import sha256_payload


def test_payload_hash_is_deterministic():
    assert sha256_payload({"b": 2, "a": 1}) == sha256_payload({"a": 1, "b": 2})


def test_trace_lifecycle(tmp_path: Path):
    r = TraceRecorder(tmp_path / "trace", actor="test")
    run = r.start_run("unit", "operation", parameters={"seed": 1})
    inp = r.register_payload({"x": 1}, role="input")
    out = r.register_payload({"y": 2}, role="output")
    r.attach_input(run.run_id, inp); r.attach_output(run.run_id, out)
    r.finish_run(run.run_id, status=TraceStatus.SUCCEEDED)
    report = verify_recorder(r)
    assert report.valid
    assert report.events_checked == 5


def test_lineage_rejects_cycle():
    g = LineageGraph(); g.add_edge("a", "b"); g.add_edge("b", "c")
    try:
        g.add_edge("c", "a")
        assert False, "cycle should fail"
    except ValueError:
        pass


def test_bundle(tmp_path: Path):
    r = TraceRecorder(tmp_path / "trace")
    run = r.start_run("demo", "x")
    out = r.register_payload({"ok": True}, role="output")
    r.attach_output(run.run_id, out); r.finish_run(run.run_id)
    path = r.export_bundle(tmp_path / "bundle.json")
    assert path.exists()
