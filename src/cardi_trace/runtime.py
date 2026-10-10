"""Read-only runtime observations, separate from caller declarations.

Never import numerical libraries or initialize an accelerator to collect provenance.
An observation describes the instant a run starts, not every operation in that run.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from importlib.metadata import PackageNotFoundError, version


NUMERICAL_DISTRIBUTIONS = (
    "numpy",
    "scipy",
    "torch",
    "jax",
    "jaxlib",
    "tensorflow",
    "cupy",
)
RUNTIME_ENVIRONMENT_KEYS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "CUBLAS_WORKSPACE_CONFIG",
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "PYTHONHASHSEED",
)


def _observe(function):
    """Keep unsupported/partially imported backends from blocking the ledger."""
    try:
        value = function()
        # Refuse nonportable objects, NaN and infinity rather than stringifying them.
        return {
            "status": "observed",
            "value": json.loads(json.dumps(value, allow_nan=False)),
        }
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__}


def _torch_settings(torch):
    return {
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
        "num_threads": torch.get_num_threads(),
        "num_interop_threads": torch.get_num_interop_threads(),
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
        "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
    }


def _torch_accelerators(torch):
    initialized = torch.cuda.is_initialized()
    # device_count/properties can initialize CUDA. Leave unavailable devices unknown.
    if not initialized:
        return {"cuda_initialized": False, "devices": None}
    devices = []
    for index in range(torch.cuda.device_count()):
        item = torch.cuda.get_device_properties(index)
        devices.append(
            {
                "index": index,
                "name": item.name,
                "compute_capability": [item.major, item.minor],
                "total_memory_bytes": item.total_memory,
            }
        )
    return {"cuda_initialized": True, "devices": devices}


def capture_runtime():
    """Capture available host/build/settings evidence without changing execution."""
    installed = {}
    for name in NUMERICAL_DISTRIBUTIONS:
        try:
            installed[name] = version(name)
        except PackageNotFoundError:
            installed[name] = None
    backends = {}
    for name in ("numpy", "scipy", "torch", "jax", "tensorflow", "cupy"):
        module = sys.modules.get(name)
        if module is None:
            backends[name] = {"status": "not_loaded"}
            continue
        item = {
            "status": "loaded",
            "version": _observe(lambda: str(module.__version__)),
        }
        if name in ("numpy", "scipy"):
            # Supported modern API returns data and never redirects process stdout.
            item["build_config"] = _observe(lambda: module.show_config(mode="dicts"))
        elif name == "torch":
            item["build_config"] = _observe(lambda: module.__config__.show())
            item["settings"] = _observe(lambda: _torch_settings(module))
            item["accelerators"] = _observe(lambda: _torch_accelerators(module))
        backends[name] = item
    return {
        "schema_version": "carditrace.runtime.v1",
        "scope": "run_start_observation_not_execution_attestation",
        "host": {
            "machine": platform.machine(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
        },
        "installed_numerical_packages": installed,
        "loaded_backends": backends,
        # Only these computation settings are collected; never enumerate credentials.
        "environment_settings": {
            key: os.environ.get(key) for key in RUNTIME_ENVIRONMENT_KEYS
        },
    }
