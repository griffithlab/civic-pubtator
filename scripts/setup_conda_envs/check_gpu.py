#!/usr/bin/env python3
"""
GPU / CUDA / TensorFlow diagnostic script.

Checks GPU hardware, NVIDIA driver, system CUDA, and whether TensorFlow
in the current Python environment can use the GPU.  Run inside the target
conda environment:

    conda run -n gnorm2-tf215 python3 scripts/setup_conda_envs/check_gpu.py

Or directly if the right Python is already active:

    python3 scripts/setup_conda_envs/check_gpu.py
"""

import ctypes
import os
import shutil
import subprocess
import sys

SEP  = "=" * 66
SEP2 = "-" * 66


def section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def run_cmd(cmd):
    """Run a shell command and return stdout, or an error string."""
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                       text=True).strip()
    except Exception as e:
        return f"(error: {e})"


# ── 1. GPU hardware ───────────────────────────────────────────────────────────
section("1. GPU hardware  (nvidia-smi)")
if shutil.which("nvidia-smi"):
    print(run_cmd(["nvidia-smi"]))
else:
    print("  nvidia-smi not found — no NVIDIA driver installed?")

# ── 2. NVIDIA driver & system CUDA ───────────────────────────────────────────
section("2. NVIDIA driver & system CUDA")
driver_ver = run_cmd(["nvidia-smi", "--query-gpu=driver_version",
                      "--format=csv,noheader"]) if shutil.which("nvidia-smi") else "n/a"
print(f"  NVIDIA driver version : {driver_ver}")

nvcc_ver = run_cmd(["nvcc", "--version"]) if shutil.which("nvcc") else "nvcc not found"
print(f"  nvcc version          : {nvcc_ver.splitlines()[-1] if nvcc_ver else 'n/a'}")

cuda_home = os.environ.get("CUDA_HOME") or os.environ.get("CUDA_PATH") or "/usr/local/cuda"
version_json = os.path.join(cuda_home, "version.json")
if os.path.exists(version_json):
    import json
    with open(version_json) as f:
        cuda_info = json.load(f)
    cuda_ver = cuda_info.get("cuda", {}).get("version", "unknown")
    print(f"  System CUDA version   : {cuda_ver}  ({cuda_home})")
else:
    print(f"  System CUDA version   : not found at {cuda_home}")

# ── 3. TensorFlow build info ──────────────────────────────────────────────────
section("3. TensorFlow in current Python environment")
print(f"  Python                : {sys.version.split()[0]}  ({sys.executable})")
try:
    import tensorflow as tf
    build = tf.sysconfig.get_build_info()
    print(f"  TensorFlow version    : {tf.__version__}")
    print(f"  TF built with CUDA    : {build.get('cuda_version', 'n/a')}")
    print(f"  TF built with cuDNN   : {build.get('cudnn_version', 'n/a')}")
    print(f"  is_built_with_cuda()  : {tf.test.is_built_with_cuda()}")
    tf_available = True
except ImportError:
    print("  TensorFlow is NOT installed in this environment.")
    tf_available = False

# ── 4. CUDA / cuDNN packages in this Python env ───────────────────────────────
section("4. CUDA-related packages installed in this environment")
pip_list = run_cmd([sys.executable, "-m", "pip", "list"])
cuda_pkgs = [l for l in pip_list.splitlines()
             if any(k in l.lower() for k in ("cuda", "cudnn", "tensorrt", "nvidia"))]
if cuda_pkgs:
    for p in cuda_pkgs:
        print(f"  {p}")
else:
    print("  (none found)")

# ── 5. Required .so files ─────────────────────────────────────────────────────
section("5. Required CUDA shared libraries (.so)")
if tf_available:
    build = tf.sysconfig.get_build_info()
    cuda_maj  = build.get('cuda_version', '12').split('.')[0]
    cudnn_maj = build.get('cudnn_version', '8').split('.')[0]
    # cuFFT soname follows CUDA major version but lags by 1 (CUDA 12 → cufft.so.11)
    cufft_maj = str(int(cuda_maj) - 1)
    required_libs = [
        f"libcuda.so.1",
        f"libcudnn.so.{cudnn_maj}",
        f"libcufft.so.{cufft_maj}",
        f"libcublas.so.{cuda_maj}",
        f"libcurand.so.{cuda_maj}",
    ]
else:
    required_libs = ["libcuda.so.1", "libcudnn.so.8", "libcufft.so.10",
                     "libcublas.so.12", "libcurand.so.12"]

all_ok = True
for lib in required_libs:
    try:
        ctypes.CDLL(lib)
        print(f"  OK      {lib}")
    except OSError as e:
        short = str(e).split(":")[0]
        print(f"  MISSING {lib}  ({short})")
        all_ok = False

# ── 6. TF GPU device visibility ───────────────────────────────────────────────
section("6. GPUs visible to TensorFlow")
if tf_available:
    import logging
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    logging.getLogger("tensorflow").setLevel(logging.ERROR)
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        for g in gpus:
            details = tf.config.experimental.get_device_details(g)
            print(f"  {g.name}")
            print(f"    device_name   : {details.get('device_name', 'n/a')}")
            print(f"    compute_cap   : {details.get('compute_capability', 'n/a')}")
    else:
        print("  No GPU devices visible to TensorFlow.")
else:
    print("  TF not available — skipping.")

# ── 7. GPU computation test ───────────────────────────────────────────────────
section("7. GPU computation test")
if tf_available and gpus:
    import time
    import tensorflow as tf  # re-import cleanly after env var set
    N = 4096
    print(f"  Matrix multiply {N}x{N} on GPU ...")
    with tf.device("/GPU:0"):
        a = tf.random.normal([N, N])
        b = tf.random.normal([N, N])
        _ = tf.matmul(a, b)  # warm-up
        t0 = time.time()
        for _ in range(5):
            c = tf.matmul(a, b)
        c.numpy()            # force execution
    elapsed = (time.time() - t0) / 5
    print(f"  GPU matmul time (avg over 5 runs): {elapsed*1000:.1f} ms  ✓  GPU is working!")
elif tf_available:
    print("  Skipped — no GPU visible to TensorFlow.")
else:
    print("  Skipped — TensorFlow not available.")

# ── 8. Summary & recommendations ─────────────────────────────────────────────
section("8. Summary & recommendations")
if tf_available:
    build = tf.sysconfig.get_build_info()
    needs_cuda  = build.get('cuda_version', 'unknown')
    needs_cudnn = build.get('cudnn_version', 'unknown')
    cudnn_maj   = needs_cudnn.split('.')[0]

    if gpus:
        print("  ✓  GPU is available and TensorFlow can use it.")
    else:
        print(f"  ✗  TensorFlow {tf.__version__} was built with CUDA {needs_cuda} / cuDNN {needs_cudnn}.")
        print()
        if not all_ok:
            print("  Missing libraries must be installed in this environment.")
            print(f"  For cuDNN {cudnn_maj}, install the matching pip package:")
            print()
            if cudnn_maj == "8":
                print("    pip install nvidia-cudnn-cu12==8.9.7.29")
                print("    pip install nvidia-cufft-cu12")
            else:
                print(f"    pip install nvidia-cudnn-cu{needs_cuda.split('.')[0]}")
            print()
        print("  After installing, you may also need to add the library path:")
        site = run_cmd([sys.executable, "-c",
                        "import site; print(site.getsitepackages()[0])"])
        print(f"    export LD_LIBRARY_PATH={site}/nvidia/cudnn/lib:$LD_LIBRARY_PATH")
        print()
        print("  Or reinstall TF with bundled CUDA support:")
        print(f"    pip install 'tensorflow[and-cuda]=={tf.__version__}'")
else:
    print("  TensorFlow is not installed in this environment.")

print()
