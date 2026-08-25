from pathlib import Path
import json

from cardi_trace import (
    TraceRecorder, TracePolicy, TracePolicyError, TraceQuery,
    compare_traces, load_bundle, create_envelope, verify_envelope,
    recorder_merkle_root, redact, plan_replay, validate_replay,
)


def build_trace(root: Path, value=1):
    r = TraceRecorder(root, actor="test", component="power")
    run = r.start_run("CardiEval", "evaluate", parameters={"seed": 42, "value": value}, seeds={"numpy": 42})
    inp = r.register_payload({"dataset": "demo", "v": value}, role="input")
    r.attach_input(run.run_id, inp)
    out = r.register_payload({"score": 0.9 + value / 100}, role="output")
    r.attach_output(run.run_id, out)
    r.add_lineage(inp.artifact_id, out.artifact_id, run_id=run.run_id)
    r.finish_run(run.run_id)
    return r, run


def test_fingerprint_and_replay(tmp_path):
    r, run = build_trace(tmp_path / "a")
    plan = plan_replay(r, run.run_id)
    candidate = next(x for x in r.runs if x.run_id == run.run_id)
    assert plan.fingerprint
    assert validate_replay(run, candidate) == ()


def test_policy_and_redaction(tmp_path):
    r = TraceRecorder(tmp_path / "trace")
    r.record("secret.test", {"token": "do-not-store", "nested": {"password": "x"}})
    event = r.events[0]
    assert event.payload["token"] == "[REDACTED]"
    assert event.payload["nested"]["password"] == "[REDACTED]"
    run = r.start_run("demo", "source")
    r.finish_run(run.run_id)
    TracePolicy().assert_compliant(r)
    assert redact({"api_key": "x", "safe": 1}) == {"api_key": "[REDACTED]", "safe": 1}


def test_bundle_merkle_and_federation(tmp_path):
    r, _ = build_trace(tmp_path / "trace")
    path = r.export_bundle(tmp_path / "bundle.json")
    bundle = load_bundle(path)
    assert bundle["schema_version"] == "2.0"
    assert bundle["commitment"]["root"] == recorder_merkle_root(r)
    env = create_envelope(r, source="CardiEval", target="CardiAtlas")
    assert verify_envelope(env, r) == ()


def test_diff_detects_change(tmp_path):
    left, _ = build_trace(tmp_path / "left", 1)
    right, _ = build_trace(tmp_path / "right", 2)
    diff = compare_traces(left, right)
    assert not diff.identical
    assert diff.changed_events > 0


def test_query_descendants(tmp_path):
    r, run = build_trace(tmp_path / "trace")
    q = TraceQuery(r)
    source = q.inputs_of(run.run_id)[0]
    assert len(q.descendants(source.artifact_id)) == 1
    assert q.latest_run(component="CardiEval").run_id == run.run_id
