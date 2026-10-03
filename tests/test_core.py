from pathlib import Path
import json
from cardi_trace import ArtifactStore, TraceRecorder, TraceStatus, TraceQuery, traced_run, verify_recorder, LineageGraph
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
    assert report.valid and report.events_checked == 6
    assert TraceQuery(r).outputs_of(run.run_id)[0].artifact_id == out.artifact_id


def test_context_success_and_failure(tmp_path: Path):
    r = TraceRecorder(tmp_path / "trace")
    with traced_run(r, "demo", "success"):
        pass
    try:
        with traced_run(r, "demo", "failure"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    statuses = {run.operation: str(run.status) for run in r.runs}
    assert statuses == {"success": "succeeded", "failure": "failed"}
    assert verify_recorder(r).valid


def test_tamper_is_detected(tmp_path: Path):
    r = TraceRecorder(tmp_path / "trace")
    run = r.start_run("unit", "operation")
    r.finish_run(run.run_id)
    lines = r.events_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0]); first["payload"]["run"]["operation"] = "tampered"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    r.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = verify_recorder(TraceRecorder(tmp_path / "trace"))
    assert not report.valid
    assert any(i.code == "event.hash" for i in report.issues)


def test_lineage_rejects_cycle():
    g = LineageGraph(); g.add_edge("a", "b"); g.add_edge("b", "c")
    try:
        g.add_edge("c", "a")
        assert False, "cycle should fail"
    except ValueError:
        pass
    assert g.topological() == ["a", "b", "c"]


def test_artifact_store(tmp_path: Path):
    store = ArtifactStore(tmp_path / "store")
    digest = store.put_bytes(b"carditrace")
    assert store.exists(digest) and store.verify(digest)
    assert store.get_bytes(digest) == b"carditrace"


def test_bundle(tmp_path: Path):
    r = TraceRecorder(tmp_path / "trace")
    run = r.start_run("demo", "x")
    out = r.register_payload({"ok": True}, role="output")
    r.attach_output(run.run_id, out); r.finish_run(run.run_id)
    path = r.export_bundle(tmp_path / "bundle.json")
    assert path.exists()
    assert "bundle_digest" in json.loads(path.read_text(encoding="utf-8"))
