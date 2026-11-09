"""Import only pinned compression evidence, never models or generated results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "fa1258135268ca2650170a3f358975ce49169290"
REPO = "https://github.com/tusharsaharan/Research"
SOURCE_DIR = "backend/data/bench/hinglish_scaleup_full_20261029"
DEST = ROOT / "backend/data/compression_evidence"
FILES = ("RESULTS.md", "verified_review.json", "stress_report.json")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    records = []
    for name in FILES:
        source = f"{SOURCE_DIR}/{name}"
        url = f"https://raw.githubusercontent.com/tusharsaharan/Research/{COMMIT}/{source}"
        with urlopen(Request(url, headers={"User-Agent": "IML-evidence-import"}), timeout=60) as response:
            content = response.read()
        if name.endswith(".json"):
            json.loads(content)
        target = DEST / name
        if target.exists() and target.read_bytes() != content:
            raise SystemExit(f"Refusing to overwrite different content: {target}")
        target.write_bytes(content)
        records.append({"source": source, "file": name, "url": url,
                        "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    manifest = {"repository": REPO, "commit": COMMIT, "kind": "historical_development_evaluation",
                "verification_scope": "Imported bytes fingerprinted; raw answer runs not rerun locally.",
                "files": records}
    target = DEST / "provenance.json"
    content = (json.dumps(manifest, indent=2) + "\n").encode()
    if target.exists() and target.read_bytes() != content:
        raise SystemExit(f"Refusing to overwrite different provenance: {target}")
    target.write_bytes(content)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
