"""One-time, cross-platform setup. Run from any directory: python scripts/setup.py."""
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".venv"
PYTHON = ENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")
if not PYTHON.exists():
    venv.create(ENV, with_pip=True)
elif subprocess.run([str(PYTHON), "-m", "pip", "--version"], capture_output=True, check=False).returncode:
    subprocess.run([str(PYTHON), "-m", "ensurepip", "--upgrade"], check=True)
subprocess.run([str(PYTHON), "-m", "pip", "install", "-e", "backend[dev]"], cwd=ROOT, check=True)
router_files = [ROOT / "backend/data/artifacts" / name for name in (
    "routing_metrics.json", "routing_logreg_coefficients.json", "routing_logistic_regression.joblib",
    "routing_random_forest.joblib", "routing_mlp.joblib",
)]
if "--retrain-router" in sys.argv or not all(path.is_file() for path in router_files):
    subprocess.run([str(PYTHON), "backend/scripts/train_router.py"], cwd=ROOT, check=True)
else:
    print("Using the saved CPU routing artifacts. Pass --retrain-router to replace them explicitly.")
npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
if not npm:
    raise SystemExit("Install Node.js 22+, then run npm install.")
subprocess.run([npm, "ci" if (ROOT / "package-lock.json").exists() else "install"], cwd=ROOT, check=True)
print("Ready. Run npm run dev, then open http://localhost:8080")
