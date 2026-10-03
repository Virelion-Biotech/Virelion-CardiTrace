"""High-level run context and decorator helpers."""
from __future__ import annotations
from contextlib import AbstractContextManager
from functools import wraps
from typing import Any, Callable, TypeVar
from .models import TraceStatus

T = TypeVar("T")


class traced_run(AbstractContextManager):
    """Context manager that records success/failure without hiding exceptions."""
    def __init__(self, recorder, component: str, operation: str, *, parameters: dict[str, Any] | None = None, code_identity: str | None = None, parent_run_id: str | None = None):
        self.recorder = recorder; self.component = component; self.operation = operation
        self.parameters = parameters or {}; self.code_identity = code_identity; self.parent_run_id = parent_run_id; self.run = None

    def __enter__(self):
        self.run = self.recorder.start_run(self.component, self.operation, parameters=self.parameters, code_identity=self.code_identity, parent_run_id=self.parent_run_id)
        return self.run

    def __exit__(self, exc_type, exc, tb):
        if self.run is None: return False
        status = TraceStatus.SUCCEEDED if exc is None else TraceStatus.FAILED
        self.recorder.finish_run(self.run.run_id, status=status, metadata={"exception": None if exc is None else type(exc).__name__})
        return False


def trace_function(recorder, *, component: str, operation: str | None = None) -> Callable:
    """Decorate a function so invocation metadata becomes a trace run."""
    def decorate(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapped(*args, **kwargs):
            op = operation or func.__name__
            with traced_run(recorder, component, op, parameters={"args_count": len(args), "kwargs": sorted(kwargs)}):
                return func(*args, **kwargs)
        return wrapped
    return decorate
