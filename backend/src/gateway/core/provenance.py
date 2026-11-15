"""Verify pinned content across Git's LF / Windows CRLF text transport.

Only a byte sequence matching the existing manifest is accepted. Binary assets
stay exact; the manifest and imported files are never rewritten.
"""
import hashlib
from pathlib import Path


def verified_source_bytes(path: Path, expected: str) -> bytes:
    raw = path.read_bytes()
    candidates = [raw]
    if path.suffix in {".py", ".json", ".md", ".jsonl", ".txt"}:
        lf = raw.replace(b"\r\n", b"\n")
        candidates.extend([lf, lf.replace(b"\n", b"\r\n")])
    for candidate in candidates:
        if hashlib.sha256(candidate).hexdigest() == expected:
            return candidate
    raise ValueError(f"Pinned source fingerprint mismatch: {path.name}")
