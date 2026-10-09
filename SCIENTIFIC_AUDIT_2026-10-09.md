# Scientific audit changes — 2026-10-09

## Behavior

Add explicit runtime identity declarations for container digests, lockfile hashes, hardware, seeds and deterministic settings; unknowns stay null. Mutable container tags are rejected.

## Scope and remaining evidence

Declarations are recorded as unverified, not inferred proof of executing hardware/settings. Callers pass the resulting environment to start_run. Existing PROV-JSON and HMAC mechanisms do not establish Workflow Run RO-Crate conformance or independent timestamp authority.

## Implementation

- `tests/test_runtime_identity.py`
- `src/cardi_trace/recorder.py`

## Verification

Regression tests accompany the changes. Repository test results are recorded in the audit completion report and draft pull request. Software regression checks do not establish numerical, biological, transport or clinical validity.
