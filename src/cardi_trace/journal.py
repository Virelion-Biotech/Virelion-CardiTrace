"""Validate and replay the canonical event journal without writing files."""

from dataclasses import replace
from .fingerprint import execution_fingerprint
from .hashing import digest_event
from .models import ArtifactRef, LineageEdge, RunRecord


def validate_chain(events):
    previous = None
    seen = set()
    for event in events:
        body = event.to_dict()
        body["event_hash"] = ""
        if (
            event.event_id in seen
            or event.previous_hash != previous
            or digest_event(body) != event.event_hash
        ):
            raise ValueError(f"Invalid event chain or hash: {event.event_id}")
        seen.add(event.event_id)
        previous = event.event_hash


def refresh_fingerprint(run):
    detail = execution_fingerprint(
        code_identity=run.code_identity,
        environment_identity=run.metadata.get("execution_fingerprint_detail", {}).get(
            "environment_identity"
        ),
        input_artifacts=run.input_artifacts,
        parameters=run.parameters,
        seeds=run.metadata.get("seeds", {}),
    )
    return replace(
        run,
        metadata={
            **run.metadata,
            "execution_fingerprint": detail.digest,
            "execution_fingerprint_detail": detail.to_dict(),
        },
    )


def replay_events(events):
    validate_chain(events)
    runs, artifacts, edges = {}, {}, {}
    for event in events:
        payload = event.payload
        if not isinstance(payload, dict):
            raise ValueError("Event payload must be an object")
        if event.event_type in {"run.started", "run.finished"}:
            run = RunRecord(**payload["run"])
            if run.run_id != event.run_id:
                raise ValueError("Run/event identity mismatch")
            if event.event_type == "run.started" and run.run_id in runs:
                raise ValueError("Duplicate run start")
            if event.event_type == "run.finished" and run.run_id not in runs:
                raise ValueError("Run finish without start")
            runs[run.run_id] = run
        elif event.event_type == "artifact.registered":
            artifact = ArtifactRef(**payload["artifact"])
            artifacts[artifact.artifact_id] = artifact
        elif event.event_type in {
            "run.input.attached",
            "run.output.attached",
            "run.metric",
            "run.tag",
        }:
            if event.run_id not in runs:
                raise ValueError("Run update without start")
            run = runs[event.run_id]
            if event.event_type.endswith(".attached"):
                aid = payload["artifact_id"]
                if aid not in artifacts:
                    raise ValueError("Attached artifact is not registered")
                field = (
                    "input_artifacts"
                    if event.event_type == "run.input.attached"
                    else "output_artifacts"
                )
                run = refresh_fingerprint(
                    replace(
                        run,
                        **{field: tuple(dict.fromkeys((*getattr(run, field), aid)))},
                    )
                )
            elif event.event_type == "run.metric":
                run = replace(
                    run,
                    metrics={
                        **run.metrics,
                        str(payload["name"]): float(payload["value"]),
                    },
                )
            else:
                run = replace(
                    run, tags={**run.tags, str(payload["name"]): str(payload["value"])}
                )
            runs[event.run_id] = run
        elif event.event_type == "lineage.edge":
            edge = LineageEdge(**payload["edge"])
            edges[(edge.source_id, edge.target_id, edge.relation)] = edge
    return runs, artifacts, list(edges.values())


def state_payload(runs, artifacts, edges):
    return {
        "runs": {k: v.to_dict() for k, v in runs.items()},
        "artifacts": {k: v.to_dict() for k, v in artifacts.items()},
        "lineage": [e.to_dict() for e in edges],
    }
