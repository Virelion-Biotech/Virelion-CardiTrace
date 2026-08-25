"""Public CardiTrace API."""
from .models import ArtifactKind, ArtifactRef, AuditIssue, LineageEdge, RunRecord, TraceEvent, TraceStatus
from .recorder import TraceRecorder
from .lineage import LineageGraph
from .audit import AuditReport, verify_recorder, verify_trace_dir
from .manifest import TraceManifest
from .store import ArtifactStore
from .export import build_bundle, export_bundle, export_jsonl, load_bundle
from .integration import trace_component_event, trace_handoff, trace_model_use
from .context import traced_run, trace_function
from .query import TraceQuery
from .fingerprint import ExecutionFingerprint, code_fingerprint, environment_fingerprint, execution_fingerprint, git_identity
from .policy import PolicyViolation, TracePolicy, TracePolicyError
from .diff import TraceDiff, compare_traces, trace_digest
from .replay import ReplayPlan, plan_replay, validate_replay
from .redaction import redact
from .telemetry import TraceSpan, export_otlp_json, spans_from_recorder
from .federation import TraceEnvelope, create_envelope, verify_envelope
from .merkle import merkle_root, recorder_merkle_root
from .schema import SCHEMA_VERSION, migrate_v1_to_v2, validate_envelope

__all__ = [
    "ArtifactKind", "ArtifactRef", "AuditIssue", "LineageEdge", "RunRecord", "TraceEvent", "TraceStatus",
    "TraceRecorder", "LineageGraph", "AuditReport", "verify_recorder", "verify_trace_dir", "TraceManifest",
    "ArtifactStore", "build_bundle", "export_bundle", "export_jsonl", "load_bundle",
    "trace_component_event", "trace_handoff", "trace_model_use", "traced_run", "trace_function", "TraceQuery",
    "ExecutionFingerprint", "code_fingerprint", "environment_fingerprint", "execution_fingerprint", "git_identity",
    "PolicyViolation", "TracePolicy", "TracePolicyError", "TraceDiff", "compare_traces", "trace_digest",
    "ReplayPlan", "plan_replay", "validate_replay", "redact", "TraceSpan", "export_otlp_json", "spans_from_recorder",
    "TraceEnvelope", "create_envelope", "verify_envelope", "merkle_root", "recorder_merkle_root",
    "SCHEMA_VERSION", "migrate_v1_to_v2", "validate_envelope",
]

__version__ = "0.2.0"
