"""CardiTrace CLI: creation, verification, inspection, export, and provenance reporting."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from .audit import verify_trace_dir
from .export import load_bundle
from .fingerprint import sha256_file
from .models import TraceStatus
from .recorder import TraceRecorder
from .merkle import recorder_merkle_root
from .provenance import graph_from_recorder
from .card import write_workflow_card
from .openlineage import export_openlineage

def cmd_hash(args): print(sha256_file(args.path)); return 0

def cmd_verify(args):
    report=verify_trace_dir(args.path); print(json.dumps(report.to_dict(),indent=2,sort_keys=True)); return 0 if report.valid else 1

def cmd_inspect(args):
    recorder=TraceRecorder(args.path); print(json.dumps({"runs":[r.to_dict() for r in recorder.runs],"artifacts":[a.to_dict() for a in recorder.artifacts],"lineage":[e.to_dict() for e in recorder.lineage],"merkle_root":recorder_merkle_root(recorder)},indent=2,sort_keys=True)); return 0

def cmd_bundle(args): print(json.dumps(load_bundle(args.path),indent=2,sort_keys=True)); return 0

def cmd_prov(args):
    graph=graph_from_recorder(TraceRecorder(args.path)); Path(args.output).parent.mkdir(parents=True,exist_ok=True); Path(args.output).write_text(graph.to_json(prov_json=args.format=="prov-json"),encoding="utf-8"); print(args.output); return 0

def cmd_card(args):
    graph=graph_from_recorder(TraceRecorder(args.path)); write_workflow_card(graph,args.output,title=args.title); print(args.output); return 0

def cmd_openlineage(args):
    export_openlineage(TraceRecorder(args.path),args.output,lifecycle=args.lifecycle); print(args.output); return 0

def cmd_demo(args):
    recorder=TraceRecorder(args.path,actor="cli-demo")
    run=recorder.start_run("demo","example",parameters={"seed":42},seeds={"python":42})
    inp=recorder.register_payload({"cases":[1,2,3]},role="input",name="demo-input"); recorder.attach_input(run.run_id,inp)
    out=recorder.register_payload({"accuracy":1.0,"n":3},role="output",name="demo-output"); recorder.attach_output(run.run_id,out); recorder.add_lineage(inp.artifact_id,out.artifact_id,run_id=run.run_id)
    recorder.finish_run(run.run_id,status=TraceStatus.SUCCEEDED)
    bundle=recorder.export_bundle(Path(args.path)/"bundle.json"); print(bundle); return 0

def main(argv=None):
    parser=argparse.ArgumentParser(prog="carditrace"); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("hash",help="SHA-256 hash a file"); p.add_argument("path",type=Path); p.set_defaults(fn=cmd_hash)
    p=sub.add_parser("verify",help="Verify a trace directory"); p.add_argument("path",type=Path); p.set_defaults(fn=cmd_verify)
    p=sub.add_parser("inspect",help="Inspect runs, artifacts, lineage, and commitment"); p.add_argument("path",type=Path); p.set_defaults(fn=cmd_inspect)
    p=sub.add_parser("bundle",help="Verify and print a bundle"); p.add_argument("path",type=Path); p.set_defaults(fn=cmd_bundle)
    p=sub.add_parser("provenance",help="Export semantic or W3C PROV-JSON provenance"); p.add_argument("path",type=Path); p.add_argument("output",type=Path); p.add_argument("--format",choices=["semantic","prov-json"],default="semantic"); p.set_defaults(fn=cmd_prov)
    p=sub.add_parser("card",help="Render a Markdown provenance card"); p.add_argument("path",type=Path); p.add_argument("output",type=Path); p.add_argument("--title",default="CardiTrace workflow"); p.set_defaults(fn=cmd_card)
    p=sub.add_parser("openlineage",help="Export OpenLineage-shaped lifecycle events"); p.add_argument("path",type=Path); p.add_argument("output",type=Path); p.add_argument("--lifecycle",choices=["all","start","terminal"],default="all"); p.set_defaults(fn=cmd_openlineage)
    p=sub.add_parser("demo",help="Create a self-verifying example trace"); p.add_argument("path",type=Path); p.set_defaults(fn=cmd_demo)
    args=parser.parse_args(argv); return args.fn(args)

if __name__ == "__main__": raise SystemExit(main())
