"""Launch a new private CPU-only Kaggle job containing an allowlisted snapshot.

Never includes .env, runtime data, credentials, browser profiles, or user prompts.
Does not change existing Kaggle notebooks or the application implementation.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from kaggle_api import call

ROOT = Path(__file__).resolve().parents[2]


def snapshot() -> tuple[str, dict]:
    paths = [ROOT / "backend/pyproject.toml", ROOT / "docs/source-manifest.json"]
    paths += list((ROOT / "backend/src").rglob("*.py"))
    paths += list((ROOT / "backend/src/gateway/lexicons").glob("*.json"))
    paths += list((ROOT / "backend/tests").glob("test_compression*.py"))
    paths += [ROOT / "backend/tests/test_health.py"]
    for folder in ("models", "tfidf", "compression_evidence", "fixtures", "router_artifacts"):
        paths += [p for p in (ROOT / "backend/data" / folder).iterdir() if p.is_file()]
    paths += [ROOT / "scripts/compression_research" / name for name in
              ("application_matrix.py", "kaggle_pilot.py", "launch_application_batch.py",
               "overnight_monitor.py", "kaggle_api.py")]
    manifest = json.loads((ROOT / "docs/source-manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        # The existing application scaffold has its own package docstring.
        # It is snapshot-hashed below, not claimed as an unchanged Research file.
        if item["destination"] == "backend/src/gateway/__init__.py":
            continue
        path = ROOT / item["destination"]
        if path in paths and hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError(f"Pinned Research fingerprint mismatch: {item['destination']}")
    buffer = io.BytesIO()
    hashes = {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            archive.writestr(name, data)
    data = buffer.getvalue()
    return base64.b64encode(data).decode(), {"sha256": hashlib.sha256(data).hexdigest(), "files": hashes}


def build_source(bundle: str, fingerprints: dict) -> str:
    return f'''# Private CPU application validation; no API keys and no new compressor.
import base64, hashlib, io, json, os, subprocess, sys, zipfile
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", USE_TF="0", OMP_NUM_THREADS="4", IML_MODE="demo")
out = Path("/kaggle/working")
root = out / "application-snapshot"
payload = base64.b64decode({bundle!r})
fingerprints = {fingerprints!r}
assert hashlib.sha256(payload).hexdigest() == fingerprints["sha256"]
root.mkdir(exist_ok=True)
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    archive.extractall(root)
for name, digest in fingerprints["files"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
(out / "snapshot-fingerprints.json").write_text(json.dumps(fingerprints, indent=2))
metadata = {{"kind":"kaggle_application_validation", "integration_approved":False, "gpu_requested":False, "cpu_count":os.cpu_count(), "status":"setup"}}
def save():
    (out / "batch-status.json").write_text(json.dumps(metadata, indent=2))
save()
try:
    setup = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-e", str(root / "backend") + "[dev]"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=900)
    (out / "setup.log").write_text(setup.stdout)
    setup.check_returncode()
    metadata["status"] = "unit_tests"
    save()
    unit = subprocess.run([sys.executable, "-m", "pytest", "tests/test_compression.py", "tests/test_compression_phrases.py", "tests/test_compression_evidence.py", "tests/test_health.py", "-q", "--junitxml=" + str(out / "application-junit.xml")], cwd=root / "backend", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=900)
    (out / "pytest.log").write_text(unit.stdout)
    print(unit.stdout, flush=True)
    metadata["pytest_exit_code"] = unit.returncode
    metadata["status"] = "dataset_matrix"
    save()
    matrix = subprocess.run([sys.executable, str(root / "scripts/compression_research/application_matrix.py"), "--output", str(out / "application")], cwd=root, timeout=5400)
    metadata["matrix_exit_code"] = matrix.returncode
    metadata["status"] = "passed" if unit.returncode == matrix.returncode == 0 else "failed"
    save()
    if metadata["status"] != "passed":
        raise RuntimeError("Application tests failed; inspect saved logs and rows.")
except Exception as error:
    metadata["status"] = "failed"
    metadata["error"] = type(error).__name__ + ": " + str(error)
    save()
    raise
finally:
    save()
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Do not update a kernel with this tool. A fresh slug is required.
    owner, _slug = args.slug.split("/", 1)
    existing = call("kernels.KernelsApiService", "ListKernels", {"user": owner, "pageSize": 100})
    if any(row.get("ref") == args.slug for row in existing.get("kernels", [])):
        raise RuntimeError("Notebook already exists; refusing to overwrite it.")
    bundle, fingerprints = snapshot()
    source = build_source(bundle, fingerprints)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "application-batch.py").write_text(source, encoding="utf-8")
    response = call("kernels.KernelsApiService", "SaveKernel", {
        "slug": args.slug, "newTitle": args.title, "text": source, "language": "python",
        "kernelType": "script", "isPrivate": True, "enableGpu": False, "enableTpu": False,
        "enableInternet": True, "kernelExecutionType": "SAVE_AND_RUN_ALL", "sessionTimeoutSeconds": 7200,
        "datasetDataSources": [], "kernelDataSources": [], "competitionDataSources": [],
    })
    if response.get("error"):
        raise RuntimeError("Kaggle rejected the batch submission.")
    (args.output / "launch.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
