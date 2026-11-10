"""One private CPU candidate evaluation after application-batch success.

The fixed evaluation script runs only on Kaggle. It never installs candidate
dependencies/models locally or enables a new Studio method.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaggle_api import call

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--application-status", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    status = json.loads(args.application_status.read_text(encoding="utf-8"))
    if status.get("status") != "passed" or status.get("kind") != "kaggle_application_validation":
        raise RuntimeError("A successful Kaggle application batch is required first.")
    owner, _slug = args.slug.split("/", 1)
    existing = call("kernels.KernelsApiService", "ListKernels", {"user": owner, "pageSize": 100})
    if any(row.get("ref") == args.slug for row in existing.get("kernels", [])):
        raise RuntimeError("Notebook already exists; refusing to overwrite it.")
    manifest = json.loads((ROOT / "docs/source-manifest.json").read_text(encoding="utf-8"))
    source = (Path(__file__).parent / "kaggle_pilot.py").read_text(encoding="utf-8")
    source = source.replace('if __name__ == "__main__":',
                            f'RESEARCH_MANIFEST = {manifest!r}\n\nif __name__ == "__main__":')
    compile(source, "candidate-pilot.py", "exec")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "candidate-pilot.py").write_text(source, encoding="utf-8")
    response = call("kernels.KernelsApiService", "SaveKernel", {
        "slug": args.slug, "newTitle": args.title, "text": source, "language": "python",
        "kernelType": "script", "isPrivate": True, "enableGpu": False, "enableTpu": False,
        "enableInternet": True, "kernelExecutionType": "SAVE_AND_RUN_ALL", "sessionTimeoutSeconds": 7200,
        "datasetDataSources": [], "kernelDataSources": [], "competitionDataSources": [],
    })
    if response.get("error"):
        raise RuntimeError("Kaggle rejected the candidate pilot.")
    (args.output / "launch.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
