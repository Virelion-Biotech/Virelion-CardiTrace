"""Dataset/run quality metrics and assertions for provenance."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass(frozen=True)
class QualityResult:
    name: str
    passed: bool
    severity: str = "error"
    value: Any = None
    threshold: Any = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self):
        return {"name":self.name,"passed":self.passed,"severity":self.severity,"value":self.value,"threshold":self.threshold,"message":self.message,"metadata":self.metadata}

@dataclass(frozen=True)
class QualityReport:
    results: tuple[QualityResult, ...]
    @property
    def passed(self): return all(r.passed or r.severity != "error" for r in self.results)
    def to_dict(self): return {"passed":self.passed,"results":[r.to_dict() for r in self.results]}

def run_quality_checks(data: Any, checks: list[tuple[str, Callable[[Any], Any]]]) -> QualityReport:
    results=[]
    for name, check in checks:
        try:
            value=check(data); passed=bool(value); results.append(QualityResult(name,passed,value=value,message="passed" if passed else "assertion returned false"))
        except Exception as exc:
            results.append(QualityResult(name,False,message=f"check raised {type(exc).__name__}: {exc}"))
    return QualityReport(tuple(results))

def common_checks(*, row_count=None, null_fraction=None, duplicate_fraction=None, min_rows=None, max_null_fraction=None, max_duplicate_fraction=None):
    checks=[]
    if row_count is not None and min_rows is not None: checks.append(("min_rows", lambda _: row_count >= min_rows))
    if null_fraction is not None and max_null_fraction is not None: checks.append(("max_null_fraction", lambda _: null_fraction <= max_null_fraction))
    if duplicate_fraction is not None and max_duplicate_fraction is not None: checks.append(("max_duplicate_fraction", lambda _: duplicate_fraction <= max_duplicate_fraction))
    return checks
