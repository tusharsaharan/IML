"""Verify and test the imported router in a separate, network-blocked process."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from import_router import DESTINATION, verify  # noqa: E402


def main() -> None:
    count = verify()
    backend = ROOT / DESTINATION / "backend"
    env = dict(os.environ, PYTHONPATH=str(backend / "src"), PYTHONDONTWRITEBYTECODE="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    for name in ("KAGGLE_API_TOKEN", "GROQ_API_KEY", "GROQ_API_KEYS", "OPENAI_API_KEY", "PYTEST_ADDOPTS"):
        env.pop(name, None)
    # The authored checks must not run with IML's already-imported gateway.
    tests = ROOT / "scripts/routing/offline_import_checks.py"
    runner = """import socket, sys, pytest
def blocked(*args, **kwargs):
    raise RuntimeError('Network access is forbidden in router import verification')
original_pair = socket.socketpair
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
def local_event_loop_pair(*args, **kwargs):
    # Windows implements asyncio's internal socketpair with loopback TCP.
    # Permit only that stdlib construction; tests still cannot open connections.
    socket.socket.connect = original_connect
    socket.socket.connect_ex = original_connect_ex
    try:
        return original_pair(*args, **kwargs)
    finally:
        socket.socket.connect = blocked
        socket.socket.connect_ex = blocked
socket.socketpair = local_event_loop_pair
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
raise SystemExit(pytest.main(sys.argv[1:]))
"""
    print(f"Verified {count} files. Testing isolated router with network blocked.", flush=True)
    subprocess.run([sys.executable, "-c", runner, "-p", "pytest_asyncio.plugin", "-c", "pyproject.toml",
                    "--import-mode=importlib", "-o", "asyncio_default_fixture_loop_scope=function",
                    "tests/test_m3.py", "tests/test_m4.py", str(tests), "-q"],
                   cwd=backend, env=env, check=True)


if __name__ == "__main__":
    main()
