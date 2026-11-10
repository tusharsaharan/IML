"""Import provenance and collision safety; not trained-router accuracy tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import import_router as importer  # noqa: E402


def manifest():
    return json.loads((ROOT / importer.MANIFEST).read_text(encoding="utf-8"))


def test_router_sources_match_pinned_manifest_without_runtime_replacement():
    assert importer.verify() == 50
    data = manifest()
    assert data["runtime_integrated"] is False
    assert data["commit"] == importer.COMMIT
    assert len(data["missing_artifacts"]) == 5
    assert all(item["destination"].startswith(importer.DESTINATION.as_posix() + "/") for item in data["files"])
    assert not any(item["destination"] == "backend/src/gateway/modules/m4_router/router.py"
                   for item in data["files"])


def test_router_selection_excludes_credentials_databases_and_other_features():
    names = [item["source"] for item in manifest()["files"]]
    assert importer.selected_paths(names + [".env", "cascade.db", "backend/src/gateway/modules/m2_compressor/x.py"]) == names
    assert not any(name.endswith((".pkl", ".pt", ".db", ".ipynb")) for name in names)


def test_missing_required_source_is_rejected():
    with pytest.raises(ValueError, match="Missing selected upstream source"):
        importer.selected_paths([])


def test_collision_preflight_refuses_import_before_any_blob_write(tmp_path, monkeypatch):
    names = [item["source"] for item in manifest()["files"]]
    calls = []

    def fake_git(source, *arguments):
        calls.append(arguments)
        if arguments[:2] == ("rev-parse", "HEAD"):
            return importer.COMMIT.encode()
        if arguments[:2] == ("remote", "get-url"):
            return (importer.REPOSITORY + ".git").encode()
        if arguments[0] == "ls-tree":
            return "\n".join(names).encode()
        raise AssertionError("No blob should be read after a collision")

    monkeypatch.setattr(importer, "git", fake_git)
    existing = tmp_path / importer.DESTINATION / names[0]
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing user work")
    with pytest.raises(FileExistsError, match="refuses to overwrite"):
        importer.import_files(tmp_path, tmp_path)
    assert existing.read_bytes() == b"existing user work"
    assert not (tmp_path / importer.MANIFEST).exists()
    assert not any(call[0] == "show" for call in calls)


def test_wrong_commit_is_rejected_before_import(tmp_path, monkeypatch):
    monkeypatch.setattr(importer, "git", lambda *_args: b"different-commit")
    with pytest.raises(ValueError, match="pinned router commit"):
        importer.import_files(tmp_path, tmp_path)
    assert not (tmp_path / importer.DESTINATION).exists()
