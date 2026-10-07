import json
from dataclasses import replace
import pytest
from cardi_trace import (
    TraceRecorder,
    verify_recorder,
    recover_from_events,
    ArtifactStore,
    Pipeline,
    Stage,
    lock_pipeline,
    changed_stages,
    compare_traces,
)
from cardi_trace.remote_cache import Cache
from cardi_trace.hashing import sha256_payload, canonical_json
from cardi_trace.provenance import ProvenanceGraph


def test_snapshot_tampering_is_detected(tmp_path):
    r = TraceRecorder(tmp_path)
    run = r.start_run("model", "fit")
    r.finish_run(run.run_id)
    data = json.loads(r.runs_path.read_text())
    data[run.run_id]["operation"] = "forged"
    r.runs_path.write_text(json.dumps(data))
    assert not verify_recorder(TraceRecorder(tmp_path)).valid


def test_recovery_rejects_tampered_journal_without_overwriting(tmp_path):
    r = TraceRecorder(tmp_path)
    r.start_run("model", "fit")
    before = r.runs_path.read_bytes()
    data = json.loads(r.events_path.read_text())
    data["payload"]["run"]["operation"] = "forged"
    r.events_path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ValueError):
        recover_from_events(tmp_path, overwrite=True)
    assert r.runs_path.read_bytes() == before


def test_running_recovery_refreshes_fingerprint(tmp_path):
    r = TraceRecorder(tmp_path)
    run = r.start_run("model", "fit")
    ref = r.register_payload({"x": 1})
    r.attach_input(run.run_id, ref)
    expected = r.runs[0].metadata["execution_fingerprint"]
    r.runs_path.unlink()
    recovered = recover_from_events(tmp_path)
    assert recovered.runs[0].metadata["execution_fingerprint"] == expected
    assert verify_recorder(recovered).valid


def test_two_recorders_do_not_lose_state_or_fork_chain(tmp_path):
    a, b = TraceRecorder(tmp_path), TraceRecorder(tmp_path)
    a.start_run("a", "one")
    b.start_run("b", "two")
    reloaded = TraceRecorder(tmp_path)
    assert len(reloaded.runs) == 2
    assert verify_recorder(reloaded).valid


def test_returned_metadata_cannot_mutate_ledger(tmp_path):
    r = TraceRecorder(tmp_path)
    run = r.start_run("model", "fit", parameters={"nested": {"x": 1}})
    run.parameters["nested"]["x"] = 2
    r.runs[0].parameters["nested"]["x"] = 3
    assert r.runs[0].parameters["nested"]["x"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_metrics_rejected(tmp_path, value):
    r = TraceRecorder(tmp_path)
    run = r.start_run("model", "fit")
    with pytest.raises(ValueError):
        r.log_metric(run.run_id, "score", value)
    assert len(r.events) == 1


def test_sensitive_tag_redacted(tmp_path):
    r = TraceRecorder(tmp_path)
    run = r.start_run("model", "fit")
    r.set_tag(run.run_id, "api_key", "sensitive-example")
    assert "sensitive-example" not in r.events_path.read_text()
    assert "sensitive-example" not in r.runs_path.read_text()


def test_stage_dependency_change_invalidates_lock():
    a, b = Pipeline(), Pipeline()
    a.add(Stage("fit", "fit", deps=("a.csv",)))
    b.add(Stage("fit", "fit", deps=("b.csv",)))
    assert changed_stages(lock_pipeline(a), lock_pipeline(b)) == ["fit"]


def test_duplicate_pipeline_outputs_rejected():
    p = Pipeline()
    p.add(Stage("a", "a", outs=("model",)))
    with pytest.raises(ValueError):
        p.add(Stage("b", "b", outs=("model",)))


def test_cache_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        Cache(tmp_path).put("../escape", {"x": 1})


def test_cas_json_uses_same_canonical_identity(tmp_path):
    value = {"unicode": "心", "set": {2, 1}}
    store = ArtifactStore(tmp_path)
    assert store.put_json(value) == sha256_payload(value)


def test_cas_rejects_corrupt_existing_blob(tmp_path):
    store = ArtifactStore(tmp_path)
    digest = store.put_bytes(b"correct")
    store._path(digest).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        store.get_bytes(digest)
    with pytest.raises(ValueError):
        store.put_bytes(b"correct")


def test_cas_gc_preserves_directory_children(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "x").write_bytes(b"x")
    store = ArtifactStore(tmp_path / "store")
    digest = store.put_directory(src)
    child = store.get_json(digest)["entries"][0]["digest"]
    assert child not in store.gc({digest})
    assert store.exists(child)


def test_trace_diff_detects_artifact_descriptor_change(tmp_path):
    a = TraceRecorder(tmp_path / "a")
    ref = a.register_payload({"x": 1})
    b = TraceRecorder(tmp_path / "b")
    b._events = list(a.events)
    b._artifacts = {ref.artifact_id: replace(ref, name="changed")}
    assert not compare_traces(a, b).identical


def test_provenance_traversal_and_specialization_export():
    g = ProvenanceGraph()
    g.entity("input")
    g.entity("output")
    g.activity("run")
    g.used("run", "input")
    g.generated("output", "run")
    assert "output" in g.downstream("input")
    assert "input" in g.upstream("output")
    g.specialized("output", "input")
    assert g.to_prov_json()["specializationOf"]


def _process_writer(root, index):
    r = TraceRecorder(root)
    for i in range(4):
        run = r.start_run("worker", f"{index}:{i}", code_identity="test:fixed")
        r.finish_run(run.run_id)


def test_concurrent_processes(tmp_path):
    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    workers = [
        ctx.Process(target=_process_writer, args=(str(tmp_path), i)) for i in range(3)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(30)
        assert worker.exitcode == 0
    trace = TraceRecorder(tmp_path)
    assert len(trace.runs) == 12
    assert len(trace.events) == 24
    assert verify_recorder(trace).valid


def test_concurrent_threads_one_recorder(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    trace = TraceRecorder(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(
            pool.map(
                lambda i: trace.start_run("thread", str(i), code_identity="test:fixed"),
                range(12),
            )
        )
    assert len({r.run_id for r in runs}) == 12
    assert len(TraceRecorder(tmp_path).runs) == 12
    assert verify_recorder(TraceRecorder(tmp_path)).valid


def test_interrupted_snapshot_requires_explicit_recovery(tmp_path, monkeypatch):
    import cardi_trace.recorder as module

    trace = TraceRecorder(tmp_path)
    original = module.atomic_json

    def fail(path, value):
        if path.name == "artifacts.json":
            raise OSError("simulated interruption")
        return original(path, value)

    monkeypatch.setattr(module, "atomic_json", fail)
    with pytest.raises(OSError):
        trace.register_payload({"x": 1})
    monkeypatch.setattr(module, "atomic_json", original)
    assert not verify_recorder(TraceRecorder(tmp_path)).valid
    assert verify_recorder(recover_from_events(tmp_path)).valid


def test_recovery_handles_malformed_snapshots_only_explicitly(tmp_path):
    trace = TraceRecorder(tmp_path)
    trace.start_run("model", "fit")
    trace.runs_path.write_text("{broken")
    with pytest.raises(ValueError):
        recover_from_events(tmp_path)
    assert verify_recorder(recover_from_events(tmp_path, overwrite=True)).valid


def test_rehashed_bundle_cannot_hide_corrupt_journal(tmp_path):
    from cardi_trace import load_bundle

    trace = TraceRecorder(tmp_path / "trace")
    trace.start_run("model", "fit")
    path = trace.export_bundle(tmp_path / "bundle.json")
    data = json.loads(path.read_text())
    data["events"][0]["payload"]["run"]["operation"] = "forged"
    data.pop("bundle_digest")
    data["bundle_digest"] = sha256_payload(data)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_bundle(path)


def test_missing_or_malformed_trace_returns_invalid_without_creation(tmp_path):
    from cardi_trace import verify_trace_dir

    root = tmp_path / "missing"
    assert not verify_trace_dir(root).valid
    assert not root.exists()
    root.mkdir()
    (root / "events.jsonl").write_text("{invalid\n")
    assert not verify_trace_dir(root).valid


def test_reserved_event_type_rejected_without_append(tmp_path):
    trace = TraceRecorder(tmp_path)
    with pytest.raises(ValueError):
        trace.record("run.started", {"run": {}})
    assert not trace.events


def test_redacted_parameters_have_consistent_execution_identity(tmp_path):
    trace = TraceRecorder(tmp_path)
    run = trace.start_run(
        "model", "fit", parameters={"token": "example"}, seeds={"secret": "example"}
    )
    trace.finish_run(run.run_id)
    assert verify_recorder(trace).valid
    assert "example" not in trace.events_path.read_text()


def test_run_finish_cannot_overwrite_identity(tmp_path):
    trace = TraceRecorder(tmp_path)
    run = trace.start_run("model", "fit")
    with pytest.raises(ValueError):
        trace.finish_run(run.run_id, status="invalid")
    with pytest.raises(ValueError):
        trace.finish_run(run.run_id, metadata={"execution_fingerprint": "forged"})
    trace.finish_run(run.run_id)
    with pytest.raises(ValueError):
        trace.finish_run(run.run_id)
    assert verify_recorder(trace).valid


def test_activity_input_failure_records_failed_run(tmp_path):
    from cardi_trace import activity

    trace = TraceRecorder(tmp_path)
    with pytest.raises(KeyError):
        with activity(trace, "model", "fit", inputs=("missing",)):
            pass
    assert trace.runs[0].status == "failed"
    assert verify_recorder(trace).valid


def test_cache_none_is_a_cache_hit(tmp_path):
    cache = Cache(tmp_path)
    key = cache.key(code="test")
    cache.put(key, None)
    assert cache.get_or_compute(key, lambda: pytest.fail("cache miss")) == (None, True)


def test_hash_rejects_colliding_keys_and_invalid_chunk_size(tmp_path):
    from cardi_trace.hashing import sha256_file

    with pytest.raises(ValueError):
        canonical_json({1: "a", "1": "b"})
    path = tmp_path / "x"
    path.write_bytes(b"abc")
    with pytest.raises(ValueError):
        sha256_file(path, 0)


def test_federation_rejects_corrupt_trace_and_omitted_artifacts(tmp_path):
    from cardi_trace import create_envelope, verify_envelope

    trace = TraceRecorder(tmp_path)
    trace.register_payload({"x": 1})
    envelope = create_envelope(trace, source="a", target="b")
    assert "artifact_set_mismatch" in verify_envelope(
        replace(envelope, artifact_ids=()), trace
    )
    trace._events[0] = replace(trace._events[0], payload={"forged": True})
    assert "invalid_trace" in verify_envelope(envelope, trace)


def test_replay_detects_environment_and_output_changes(tmp_path):
    from cardi_trace import validate_replay

    trace = TraceRecorder(tmp_path)
    run = trace.start_run("model", "fit")
    trace.finish_run(run.run_id)
    run = trace.runs[0]
    assert "environment" in validate_replay(
        run, replace(run, environment={"different": True})
    )
    assert "outputs" in validate_replay(
        run, replace(run, output_artifacts=("different",))
    )


def test_removed_producer_invalidates_consumer():
    old = {
        "stages": {
            "a": {"digest": "1", "stage_deps": []},
            "b": {"digest": "2", "stage_deps": ["a"]},
        }
    }
    new = {"stages": {"b": {"digest": "2", "stage_deps": []}}}
    assert changed_stages(old, new) == ["b"]


def test_campaign_accepts_generator_ids(tmp_path):
    from cardi_trace import summarize_campaign

    trace = TraceRecorder(tmp_path)
    a = trace.start_run("model", "a")
    b = trace.start_run("model", "b")
    assert (
        summarize_campaign(trace, run_ids=(x for x in [a.run_id, b.run_id]))[
            "run_count"
        ]
        == 2
    )


def test_unknown_package_does_not_drop_installed_versions():
    from cardi_trace.recorder import default_environment

    env = default_environment(packages=("missing-carditrace-test-package", "pytest"))
    assert env["packages"]["missing-carditrace-test-package"] is None
    assert env["packages"]["pytest"]


def test_code_identity_detects_staged_and_untracked_changes(tmp_path):
    import subprocess
    from cardi_trace import git_identity

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True
        )

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    path = tmp_path / "code.py"
    path.write_text("x=1\n")
    git("add", ".")
    git("commit", "-m", "initial")
    initial = git_identity(tmp_path)
    path.write_text("x=2\n")
    git("add", ".")
    staged = git_identity(tmp_path)
    assert staged != initial and "+dirty:" in staged
    (tmp_path / "new.py").write_text("y=1\n")
    assert git_identity(tmp_path) != staged


def test_openlineage_roundtrip_is_idempotent_and_preserves_metrics_and_descriptors(
    tmp_path,
):
    from cardi_trace import events_from_recorder, ingest_openlineage_event

    source, target = (
        TraceRecorder(tmp_path / "source"),
        TraceRecorder(tmp_path / "target"),
    )
    run = source.start_run("model", "fit", parameters={"x": 1}, tags={"split": "test"})
    ref = source.register_payload({"data": [1, 2]}, kind="dataset")
    source.attach_input(run.run_id, ref)
    source.attach_output(run.run_id, ref)
    source.log_metric(run.run_id, "score", 0.9)
    source.finish_run(run.run_id)
    events = events_from_recorder(source)
    assert events[0]["outputs"] == []
    assert events[0]["run"]["facets"]["carditrace_execution"]["metrics"] == {}
    for event in events:
        ingest_openlineage_event(target, event)
    before = len(target.events)
    for event in events:
        ingest_openlineage_event(target, event)
    assert len(target.events) == before
    assert len(target.runs) == 1
    assert target.runs[0].metrics == {"score": 0.9}
    assert target.runs[0].tags["split"] == "test"
    assert target.runs[0].input_artifacts and target.runs[0].output_artifacts
    assert all(a.metadata["content_verified"] is False for a in target.artifacts)
    assert verify_recorder(target).valid


def test_strict_file_verification_and_cli_recovery(tmp_path, capsys):
    from cardi_trace.cli import main

    path = tmp_path / "input"
    path.write_text("input")
    root = tmp_path / "trace"
    trace = TraceRecorder(root)
    trace.register_file(path, kind="dataset")
    path.unlink()
    assert main(["verify", str(root)]) == 0
    assert main(["verify", str(root), "--strict-files"]) == 1
    trace.artifacts_path.write_text("{broken")
    assert main(["recover", str(root)]) == 1
    assert main(["recover", str(root), "--overwrite"]) == 0
    assert "JSONDecodeError" in capsys.readouterr().err


def test_provenance_preserves_recorded_actor_on_reload(tmp_path):
    from cardi_trace import graph_from_recorder

    trace = TraceRecorder(tmp_path, actor="original-actor")
    run = trace.start_run("model", "fit")
    graph = graph_from_recorder(TraceRecorder(tmp_path))
    assert any(
        r.source == f"activity:{run.run_id}" and r.target == "agent:original-actor"
        for r in graph.relations
    )


def test_cache_detects_corrupted_value_and_legacy_entries(tmp_path):
    cache = Cache(tmp_path)
    key = cache.key(code="fixed")
    path = cache.put(key, {"value": 1})
    content = json.loads(path.read_text())
    content["value"]["value"] = 2
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError):
        cache.get(key)
    path.write_text(json.dumps({"value": 1}))
    with pytest.raises(ValueError):
        cache.get(key)


def test_cas_read_only_open_and_bad_paths(tmp_path):
    store = ArtifactStore(tmp_path)
    digest = store.put_bytes(b"abc")
    with store.open(digest) as handle:
        assert handle.read() == b"abc"
    with pytest.raises(ValueError):
        store.open(digest, "wb")
    with pytest.raises(ValueError):
        store.get_bytes("../escape")
    with pytest.raises(ValueError):
        store.get_bytes(digest.upper())


def test_relative_storage_roots_survive_working_directory_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    trace = TraceRecorder("trace")
    store = ArtifactStore("store")
    cache = Cache("cache")
    digest = store.put_bytes(b"fixed")
    key = cache.key(code="fixed")
    cache.put(key, 1)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    trace.start_run("model", "fit")
    assert (tmp_path / "trace" / "events.jsonl").exists()
    assert store.get_bytes(digest) == b"fixed"
    assert cache.get(key) == 1
    assert not (other / "trace").exists()


def test_nested_telemetry_uses_parent_trace_and_span(tmp_path):
    from cardi_trace import spans_from_recorder

    trace = TraceRecorder(tmp_path)
    parent = trace.start_run("pipeline", "parent")
    child = trace.start_run("model", "child", parent_run_id=parent.run_id)
    grandchild = trace.start_run("model", "grandchild", parent_run_id=child.run_id)
    spans = {s.name: s for s in spans_from_recorder(trace)}
    assert spans["model.child"].trace_id == spans["pipeline.parent"].trace_id
    assert spans["model.child"].parent_span_id == spans["pipeline.parent"].span_id
    assert spans["model.grandchild"].trace_id == spans["pipeline.parent"].trace_id
    assert spans["model.grandchild"].parent_span_id == spans["model.child"].span_id
