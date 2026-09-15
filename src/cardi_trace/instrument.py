"""Low-friction runtime instrumentation for functions and context-managed activities."""
from __future__ import annotations
import functools, time, traceback
from contextlib import contextmanager
from typing import Any, Callable, Iterator
from .models import TraceStatus

@contextmanager
def activity(recorder, component: str, operation: str, *, inputs=(), parameters=None, metadata=None, code_identity=None, parent_run_id=None, seeds=None, packages=()) -> Iterator[Any]:
    """Record one activity without requiring callers to manage start/finish manually."""
    run = recorder.start_run(component, operation, parameters=parameters, metadata=metadata, code_identity=code_identity, parent_run_id=parent_run_id, seeds=seeds, packages=packages)
    for item in inputs:
        recorder.attach_input(run.run_id, item)
    started = time.perf_counter()
    try:
        yield run
    except BaseException as exc:
        recorder.finish_run(run.run_id, status=TraceStatus.FAILED, metadata={"exception_type": type(exc).__name__, "exception_message": str(exc), "elapsed_seconds": time.perf_counter() - started, "traceback": traceback.format_exc(limit=20)})
        raise
    else:
        recorder.finish_run(run.run_id, status=TraceStatus.SUCCEEDED, metadata={"elapsed_seconds": time.perf_counter() - started})

def traced(recorder, component: str | None = None, operation: str | None = None, *, parameters: Callable[..., dict[str, Any]] | None = None):
    """Decorator for automatic run capture; return values are not serialized automatically."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            params = parameters(*args, **kwargs) if parameters else {"args_count": len(args), "kwargs": sorted(kwargs)}
            with activity(recorder, component or fn.__module__, operation or fn.__qualname__, parameters=params):
                return fn(*args, **kwargs)
        return wrapper
    return decorate

def record_result(recorder, run_id: str, value: Any, *, role="output", name=None, media_type="application/json", metadata=None):
    """Hash and attach a function result as an artifact."""
    ref = recorder.register_payload(value, role=role, name=name, media_type=media_type, metadata=metadata)
    recorder.attach_output(run_id, ref)
    return ref
