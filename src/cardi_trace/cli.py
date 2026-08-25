"""CardiTrace CLI."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .audit import verify_trace_dir
from .hashing import sha256_file
from .recorder import TraceRecorder
from .models import TraceStatus


def cmd_hash(args):
    print(sha256_file(args.path))


def cmd_verify(args):
    report = verify_trace_dir(args.path)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.valid else 1


def cmd_demo(args):
    recorder = TraceRecorder(args.path, actor="cli-demo")
    run = recorder.start_run("demo", "example", parameters={"seed": 42})
    inp = recorder.register_payload({"cases": [1, 2, 3]}, role="input", name="demo-input")
    recorder.attach_input(run.run_id, inp)
    out = recorder.register_payload({"accuracy": 1.0, "n": 3}, role="output", name="demo-output")
    recorder.attach_output(run.run_id, out)
    recorder.finish_run(run.run_id, status=TraceStatus.SUCCEEDED)
    bundle = recorder.export_bundle(Path(args.path) / "bundle.json")
    print(bundle)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carditrace")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("hash", help="SHA-256 hash a file"); p.add_argument("path", type=Path); p.set_defaults(fn=cmd_hash)
    p = sub.add_parser("verify", help="Verify a trace directory"); p.add_argument("path", type=Path); p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("demo", help="Create a self-verifying example trace"); p.add_argument("path", type=Path); p.set_defaults(fn=cmd_demo)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__": raise SystemExit(main())
