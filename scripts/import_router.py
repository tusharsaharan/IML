"""Import a pinned router-only Git selection without overwriting IML files.

Copies committed blobs rather than checkout bytes: dirty files, CRLF conversion,
untracked credentials and model artifacts cannot enter this source transfer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/tusharsaharan/code-mixed-gateway"
COMMIT = "224d609237fcc67b5b83e029a9406e9fb7f51329"
DESTINATION = Path("backend/scripts/reference/code_mixed_gateway_router")
MANIFEST = Path("docs/router-source-manifest.json")
ATTRIBUTES = b"# IML import metadata: retain exact upstream Git-blob bytes.\n* -text\n"
SELECTION = (
    "README.md", ".gitignore", "backend/README.md", "backend/pyproject.toml",
    "backend/src/gateway/__init__.py", "backend/src/gateway/schemas.py",
    "backend/src/gateway/llm.py", "backend/src/gateway/pricing.py", "backend/src/gateway/tokenizer.py",
    "backend/src/gateway/modules/__init__.py",
    "backend/src/gateway/modules/m1_pipeline/__init__.py",
    "backend/src/gateway/modules/m1_pipeline/hinglish.py",
    "backend/src/gateway/modules/m3_conformal/",
    "backend/src/gateway/modules/m4_router/",
    "backend/src/gateway/modules/m10_train/__init__.py",
    "backend/src/gateway/modules/m10_train/reward.py",
    "backend/src/gateway/modules/m11_calibration/__init__.py",
    "backend/src/gateway/modules/m11_calibration/ece.py",
    "backend/src/gateway/modules/m12_semantic/__init__.py",
    "backend/src/gateway/modules/m12_semantic/embeddings.py",
    "backend/scripts/router_track/", "backend/scripts/freeze_splits.py",
    "backend/notebooks/README_ROUTER_RL.md", "backend/tests/test_m3.py", "backend/tests/test_m4.py",
    "backend/experiments/cascade_routing/scripts/difficulty.py",
    "backend/experiments/cascade_routing/scripts/conformal.py",
    "backend/experiments/cascade_routing/scripts/calibrate_v2.py",
    "backend/experiments/cascade_routing/scripts/calibrate_laya.py",
    "backend/experiments/cascade_routing/scripts/score_laya.py",
    "backend/experiments/cascade_routing/scripts/route_prompts_laya.py",
    "backend/experiments/cascade_routing/data/calibration_v2.csv",
    "backend/experiments/cascade_routing/data/calibration_laya.csv",
)
MISSING_ARTIFACTS = (
    "backend/data/router_artifacts/logreg.pkl",
    "backend/data/router_artifacts/xgb.json",
    "backend/data/router_artifacts/bandit_head.pt",
    "backend/data/thresholds.json", "backend/data/calibration_real.jsonl",
)
EXCLUSIONS = (
    "Credentials, .env files, databases, scratch scripts, Git history and unrelated UI/compression code",
    "Raw prompt/answer corpora, notebook outputs, report PDFs and figures (no application metrics imported)",
    "External Laya implementation/checkpoints and optional downloaded models",
    "gateway.service and its compression/gateway dependency tree; run00_audit.py remains reference-only",
)


def git(source: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=source)


def selected_paths(tracked: list[str]) -> list[str]:
    selected = set()
    for entry in SELECTION:
        matches = [name for name in tracked if name.startswith(entry)] if entry.endswith("/") else [
            name for name in tracked if name == entry
        ]
        if not matches:
            raise ValueError(f"Missing selected upstream source: {entry}")
        selected.update(matches)
    return sorted(selected)


def verify(root: Path = ROOT) -> int:
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    if manifest["repository"] != REPOSITORY or manifest["commit"] != COMMIT:
        raise ValueError("Router manifest source does not match the pinned import.")
    if (root / DESTINATION / ".gitattributes").read_bytes() != ATTRIBUTES:
        raise ValueError("Router import must retain its exact-byte Git attributes.")
    for item in manifest["files"]:
        expected_path = (DESTINATION / item["source"]).as_posix()
        if item["destination"] != expected_path or ".." in Path(item["source"]).parts:
            raise ValueError("Router manifest contains an unexpected destination.")
        data = (root / item["destination"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"Router source fingerprint mismatch: {item['destination']}")
    expected = selected_paths([item["source"] for item in manifest["files"]])
    if expected != sorted(item["source"] for item in manifest["files"]):
        raise ValueError("Router manifest includes unexpected files.")
    return len(expected)


def import_files(source: Path, root: Path = ROOT) -> int:
    if git(source, "rev-parse", "HEAD").decode().strip() != COMMIT:
        raise ValueError(f"Check out the pinned router commit {COMMIT} first.")
    remote = git(source, "remote", "get-url", "origin").decode().strip().removesuffix(".git")
    if remote != REPOSITORY:
        raise ValueError("Expected the code-mixed-gateway origin URL.")
    tracked = git(source, "ls-tree", "-r", "--name-only", COMMIT).decode().splitlines()
    names = selected_paths(tracked)
    # Preflight every collision before writing anything, including the manifest.
    targets = [root / DESTINATION / name for name in names] + [root / MANIFEST,
                                                              root / DESTINATION / ".gitattributes"]
    collisions = [str(path) for path in targets if path.exists()]
    if collisions:
        raise FileExistsError("Router import refuses to overwrite files: " + ", ".join(collisions))
    blobs = [(name, git(source, "show", f"{COMMIT}:{name}")) for name in names]
    manifest = {
        "repository": REPOSITORY, "commit": COMMIT,
        "kind": "isolated_router_reference_import", "runtime_integrated": False,
        "source_bytes": "exact Git blobs; no algorithm edits or checkout newline conversions",
        "authored_support_files": [(DESTINATION / ".gitattributes").as_posix()],
        "license": "No licence file or declared repository licence found at the pinned commit; not inferred.",
        "missing_artifacts": [name for name in MISSING_ARTIFACTS if name not in tracked],
        "exclusions": list(EXCLUSIONS), "files": [],
    }
    for name, data in blobs:
        relative = DESTINATION / name
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["files"].append({"source": name, "destination": relative.as_posix(),
                                  "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    (root / DESTINATION / ".gitattributes").write_bytes(ATTRIBUTES)
    (root / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return verify(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        count = verify()
        print(f"Verified {count} pinned router reference files.")
    elif args.source:
        count = import_files(args.source.resolve())
        print(f"Imported {count} files from code-mixed-gateway@{COMMIT[:12]} into {DESTINATION}.")
    else:
        parser.error("Specify --source or --verify.")


if __name__ == "__main__":
    main()
