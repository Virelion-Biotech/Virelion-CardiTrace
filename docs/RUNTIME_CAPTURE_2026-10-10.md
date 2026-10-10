# Runtime capture: audit recommendation 20.03

The default recorder previously recorded runtime hardware and determinism as caller
declarations, with unknown defaults. Default runs now also capture read-only
observations of the process that starts the run. The existing declaration fields
and `runtime_declarations_verified: false` retain their original meaning.

## Captured observations

- Host machine, processor description and logical CPU count.
- Installed NumPy, SciPy, PyTorch, JAX/JAXlib, TensorFlow and CuPy distribution versions.
- Loaded numerical module versions; NumPy/SciPy build configuration where the
  dictionary-returning API is supported; PyTorch build configuration, thread counts,
  deterministic/warn-only flags and cuDNN/matmul TF32 settings.
- Visible GPU properties only when the caller has already initialized PyTorch CUDA.
- An explicit allowlist of thread-count, accelerator-visibility, hash-seed and
  cuBLAS-workspace environment variables. No arbitrary environment enumeration.

Installed packages, loaded modules, unavailable probes and unknown devices are
distinct states. The collector imports no numerical libraries, performs no device
initialization, and makes no settings or RNG mutations. A partially imported or
unsupported backend produces an unavailable probe, rather than a false assertion.
The snapshot is included in the existing environment/execution fingerprint and
persisted through the normal hash-checked ledger.

The build APIs describe how a library was compiled. They do not prove which kernel
ran. Likewise CUDA visibility and initialized-device properties do not establish
that any particular GPU was used for an analysis.

## Remaining work

Recommendation 20.03 remains partial. Container-image attestation requires trusted
deployment/runtime support. Callers must still supply the actual dependency lockfile
and declared seeds; recording a seed does not demonstrate it was applied. Manually
supplied environments are not silently replaced. JAX, TensorFlow and CuPy device
introspection, end-of-run changes, execution-level backend/device attribution and
distributed worker identities require further integrations. These records do not
establish biological validity, deterministic execution or an independent trust anchor.

## Verification

Regression tests cover real NumPy build capture without stdout or RNG changes,
uninitialized/initialized CUDA branches with controlled API fixtures, missing/partial
backends, credential exclusion, caller-controlled environments, setting-dependent
fingerprints, persisted observations and ledger verification. Hosted CI also runs
the package integrity/recovery suite on Python 3.10–3.13 on Linux and Windows.
No real GPU capture is asserted from the controlled CUDA fixtures.

API references:

- https://numpy.org/doc/stable/reference/generated/numpy.show_config.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.show_config.html
- https://docs.pytorch.org/docs/stable/cuda.html
- https://docs.pytorch.org/docs/stable/generated/torch.are_deterministic_algorithms_enabled.html
