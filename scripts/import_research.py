"""Copy an explicit, reproducible source selection from a local Research checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = [
    "backend/src/gateway/__init__.py", "backend/src/gateway/schemas.py",
    "backend/src/gateway/llm.py", "backend/src/gateway/tokenizer.py",
    "backend/src/gateway/pricing.py", "backend/src/gateway/lexicons",
    "backend/src/gateway/modules/__init__.py",
    "backend/src/gateway/modules/m1_pipeline/__init__.py",
    "backend/src/gateway/modules/m1_pipeline/hinglish.py",
    "backend/src/gateway/modules/m2_compressor",
    "backend/src/gateway/modules/m3_conformal",
    "backend/src/gateway/modules/m4_router",
    "backend/src/gateway/modules/m10_train/__init__.py",
    "backend/src/gateway/modules/m10_train/reward.py",
    "backend/src/gateway/modules/m12_semantic",
    "backend/data/models/crf_compressor.pkl",
    "backend/data/router_artifacts", "backend/data/tfidf",
    "backend/data/training/bootstrap_filtered.jsonl",
    "src/components/ui/button.tsx", "src/components/ui/card.tsx",
    "src/components/ui/badge.tsx", "src/components/ui/input.tsx",
    "src/components/ui/textarea.tsx", "src/components/ui/skeleton.tsx",
    "src/lib/utils.ts",
]
REFERENCES = ["train_crf.py", "build_tfidf.py", "bench/router_train.py", "bench/router_baselines.py", "bench/router_v2.py"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.source, text=True).strip()
    pairs = []
    for selected in SELECTION:
        path = args.source / selected
        if not path.exists():
            raise SystemExit(f"Missing selected source: {path}")
        for src in sorted(path.rglob("*")) if path.is_dir() else [path]:
            if src.is_file() and "__pycache__" not in src.parts:
                pairs.append((src, src.relative_to(args.source)))
    for name in REFERENCES:
        src = args.source / "backend/scripts" / name
        pairs.append((src, Path("backend/scripts/reference") / name))
    collisions = [str(dst) for _, dst in pairs if (ROOT / dst).exists()]
    if collisions:
        raise SystemExit("Import refuses to overwrite existing files: " + ", ".join(collisions))
    manifest = {"repository": "https://github.com/tusharsaharan/Research", "commit": commit, "files": []}
    for src, relative in pairs:
        dst = ROOT / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        manifest["files"].append({"source": src.relative_to(args.source).as_posix(), "destination": relative.as_posix(), "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()})
    output = ROOT / "docs/source-manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(pairs)} files from Research@{commit[:12]}")


if __name__ == "__main__":
    main()
