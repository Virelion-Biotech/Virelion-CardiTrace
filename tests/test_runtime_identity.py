import pytest
from cardi_trace.recorder import default_environment


def test_default_run_observes_host_and_keeps_declarations_unverified(tmp_path):
    from cardi_trace import TraceRecorder, verify_recorder
    from cardi_trace.hashing import sha256_payload

    recorder = TraceRecorder(tmp_path)
    run = recorder.start_run("model", "fit")
    observed = run.environment["observed_runtime"]
    assert observed["schema_version"] == "carditrace.runtime.v1"
    assert "logical_cpu_count" in observed["host"]
    assert run.environment["hardware"] is None
    assert run.environment["runtime_declarations_verified"] is False
    assert run.environment["fingerprint"] == sha256_payload(
        {k: v for k, v in run.environment.items() if k != "fingerprint"}
    )
    assert TraceRecorder(tmp_path).runs[0].environment == run.environment
    assert verify_recorder(recorder).valid


def test_capture_does_not_import_backends_or_collect_credentials(monkeypatch):
    import sys
    from cardi_trace.runtime import capture_runtime

    for name in ("numpy", "scipy", "torch", "jax", "tensorflow", "cupy"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-appear")
    monkeypatch.setenv("OMP_NUM_THREADS", "7")
    result = capture_runtime()
    assert all(v["status"] == "not_loaded" for v in result["loaded_backends"].values())
    assert "torch" not in sys.modules and "numpy" not in sys.modules
    assert result["environment_settings"]["OMP_NUM_THREADS"] == "7"
    assert "must-not-appear" not in str(result)


def test_real_numpy_build_capture_preserves_rng_and_stdout(capsys):
    import numpy as np
    from cardi_trace.runtime import capture_runtime

    before = np.random.get_state()
    result = capture_runtime()["loaded_backends"]["numpy"]
    after = np.random.get_state()
    assert result["build_config"]["value"] == np.show_config(mode="dicts")
    assert result["version"]["value"] == np.__version__
    assert before[0] == after[0] and np.array_equal(before[1], after[1])
    assert before[2:] == after[2:]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("initialized", [False, True])
def test_torch_accelerator_capture_never_initializes_cuda(monkeypatch, initialized):
    import sys
    from types import SimpleNamespace as NS
    from cardi_trace.runtime import capture_runtime

    calls = []

    def count():
        assert initialized, "CUDA was probed before initialization"
        calls.append("count")
        return 1

    torch = NS(
        __version__="test",
        __config__=NS(show=lambda: "BLAS=test"),
        are_deterministic_algorithms_enabled=lambda: True,
        is_deterministic_algorithms_warn_only_enabled=lambda: False,
        get_num_threads=lambda: 4,
        get_num_interop_threads=lambda: 2,
        backends=NS(
            cudnn=NS(deterministic=True, benchmark=False, allow_tf32=False),
            cuda=NS(matmul=NS(allow_tf32=False)),
        ),
        cuda=NS(
            is_initialized=lambda: initialized,
            device_count=count,
            get_device_properties=lambda i: NS(
                name="test GPU", major=7, minor=5, total_memory=1000
            ),
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    observed = capture_runtime()["loaded_backends"]["torch"]
    assert observed["settings"]["value"]["deterministic_algorithms"] is True
    devices = observed["accelerators"]["value"]["devices"]
    assert (devices is not None) == initialized
    assert calls == (["count"] if initialized else [])
    assert observed["build_config"]["value"] == "BLAS=test"


def test_partial_backend_is_explicitly_unavailable(monkeypatch):
    import sys
    from types import SimpleNamespace
    from cardi_trace.runtime import capture_runtime

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace())
    result = capture_runtime()["loaded_backends"]["torch"]
    assert result["settings"]["status"] == "unavailable"
    assert result["accelerators"]["status"] == "unavailable"
    assert result["build_config"]["status"] == "unavailable"


def test_observed_settings_change_execution_identity(tmp_path, monkeypatch):
    from cardi_trace import TraceRecorder

    recorder = TraceRecorder(tmp_path)
    monkeypatch.setenv("OMP_NUM_THREADS", "1")
    a = recorder.start_run("model", "fit")
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    b = recorder.start_run("model", "fit")
    assert a.environment["fingerprint"] != b.environment["fingerprint"]


def test_explicit_environment_remains_caller_controlled(tmp_path):
    from cardi_trace import TraceRecorder

    env = {"source": "external-runner"}
    run = TraceRecorder(tmp_path).start_run("model", "fit", environment=env)
    assert env == {"source": "external-runner"}
    assert "observed_runtime" not in run.environment


def test_runtime_identity_tracks_unknowns_and_hashes_actual_lockfile(tmp_path):
    assert default_environment()["container_digest"] is None
    lock = tmp_path / "lock.txt"
    lock.write_text("numpy==2.2.6\n")
    a = default_environment(lockfile=lock, random_seeds={"numpy": 4})
    lock.write_text("numpy==2.2.5\n")
    b = default_environment(lockfile=lock, random_seeds={"numpy": 4})
    assert a["lockfile_sha256"] != b["lockfile_sha256"]
    assert a["runtime_declarations_verified"] is False
    with pytest.raises(ValueError):
        default_environment(container_digest="latest")
