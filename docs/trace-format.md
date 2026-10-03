# CardiTrace trace format v1

A trace bundle is JSON with five top-level fields:

- `schema_version`: currently `1.0`.
- `events`: ordered append-only event records.
- `runs`: logical computation records.
- `artifacts`: content-addressed artifact references.
- `audit`: verification result embedded at export time.
- `bundle_digest`: SHA-256 over the preceding fields in canonical form.

## Event requirements

Every event must have a unique `event_id`, a Unix timestamp, `event_type`, actor, component, payload, `previous_hash`, and `event_hash`. The event hash is calculated after setting `event_hash` to an empty string; this removes circularity while binding every other field.

## Artifact identity

Artifact IDs use the form `sha256:<hex>`. The digest is the SHA-256 of canonical JSON for payload artifacts or raw bytes for file artifacts.

## Run requirements

Runs must use a stable `run_id` and record status. Terminal statuses should include `finished_at`. Input and output artifact IDs must resolve against the artifact registry.

## Extension policy

Unknown metadata keys are allowed. Core fields are not silently reinterpreted. A future schema should increment the major/minor schema version and provide a migration path where semantics change.
