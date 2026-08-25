from cardi_trace import TraceRecorder, TraceStatus, LineageGraph, verify_recorder
from cardi_trace.integration import trace_handoff

recorder = TraceRecorder("./trace", actor="example")
g = LineageGraph()

run = recorder.start_run(
    component="CardiAgent",
    operation="generate",
    parameters={"seed": 42, "count": 8},
    code_identity="git:example-agent-commit",
)

agent = recorder.register_payload({"component": "CardiAgent", "cases": 8}, role="output", name="agent-batch")
recorder.attach_output(run.run_id, agent)
recorder.record("generation.completed", {"count": 8}, run_id=run.run_id, component="CardiAgent")
recorder.finish_run(run.run_id, status=TraceStatus.SUCCEEDED)

handoff = trace_handoff(
    recorder,
    source="CardiAgent",
    target="CardiVex",
    payload={"artifact_id": agent.artifact_id, "schema": "challenge-v1"},
)
g.add_edge(agent.artifact_id, handoff.artifact_id, relation="handed_off")

print("audit:", verify_recorder(recorder).to_dict())
print("lineage:", g.to_dict())
print("bundle:", recorder.export_bundle("./trace/bundle.json"))
