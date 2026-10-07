"""Exercise installed CLI entry points and packaged schemas without test dependencies."""

import argparse
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import cardi_trace
from cardi_trace import ArtifactStore, TraceRecorder, load_bundle, verify_recorder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if args.installed:
        assert Path(cardi_trace.__file__).parent.parent.name != "src", (
            cardi_trace.__file__
        )
    for name in ("carditrace-artifact-v1.json", "carditrace-execution-v1.json"):
        assert json.loads(files("cardi_trace").joinpath("facets", name).read_text())
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "trace"

        def cli(*arguments, ok=True):
            result = subprocess.run(
                [sys.executable, "-m", "cardi_trace.cli", *map(str, arguments)],
                capture_output=True,
                text=True,
            )
            assert (result.returncode == 0) == ok, result.stderr
            return result

        cli("demo", root)
        assert json.loads(cli("verify", root).stdout)["valid"]
        assert load_bundle(root / "bundle.json")["schema_version"] == "2.0"
        for command, filename in [
            ("provenance", "prov.json"),
            ("card", "card.md"),
            ("openlineage", "ol.jsonl"),
        ]:
            cli(command, root, Path(temp) / filename)
        trace = TraceRecorder(root)
        assert verify_recorder(trace).valid
        store = ArtifactStore(Path(temp) / "cas")
        data = b"independent byte-hash fixture"
        assert store.put_bytes(data) == hashlib.sha256(data).hexdigest()
        state = {"schema_version": "1.3.0", "entity_id": "smoke", "observations": []}
        expected = hashlib.sha256(
            json.dumps(
                state,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                default=str,
            ).encode()
        ).hexdigest()
        payload = {
            "entity_id": "smoke",
            "workflow_state": {"cardiac_state": state},
            "canonical_state_fingerprint": expected,
        }
        env = dict(
            os.environ,
            HEARTTWIN_PAYLOAD_STDIN="1",
            CARDITRACE_ROOT=str(Path(temp) / "adapter"),
        )
        result = subprocess.run(
            [sys.executable, "-m", "cardi_trace.hearttwin_adapter"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["canonical_state_verified"]
        state["entity_id"] = "tampered"
        result = subprocess.run(
            [sys.executable, "-m", "cardi_trace.hearttwin_adapter"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
        )
        assert result.returncode == 1
        assert len(TraceRecorder(Path(temp) / "adapter").runs) == 1
        cli("verify", Path(temp) / "missing", ok=False)
    print(json.dumps({"version": cardi_trace.__version__, "package_smoke": "passed"}))


if __name__ == "__main__":
    main()
