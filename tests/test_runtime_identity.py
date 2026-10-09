import pytest
from cardi_trace.recorder import default_environment


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
