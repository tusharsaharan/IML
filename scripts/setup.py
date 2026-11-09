"""One-time, cross-platform setup. Run from any directory: python scripts/setup.py."""
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".venv"
PYTHON = ENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")
if not PYTHON.exists():
    venv.create(ENV, with_pip=True)
subprocess.run([str(PYTHON), "-m", "pip", "install", "-e", "backend[dev]"], cwd=ROOT, check=True)
subprocess.run([str(PYTHON), "backend/scripts/train_router.py"], cwd=ROOT, check=True)
npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
if not npm:
    raise SystemExit("Install Node.js 22+, then run npm install.")
subprocess.run([npm, "ci" if (ROOT / "package-lock.json").exists() else "install"], cwd=ROOT, check=True)
print("Ready. Run npm run dev, then open http://localhost:8080")
