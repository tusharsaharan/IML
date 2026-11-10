"""Bounded application checks: 20 scheduled slots, 30 minutes apart.

No keep-alive traffic, GPU jobs, indefinite retries, automatic integration, or
source edits. Timer execution requires this computer to be on and awake.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kaggle_api import call, read_progress

ROOT = Path(__file__).resolve().parents[2]
INTERVAL_SECONDS = 1800
CHECK_COUNT = 20
STATUSES = {0: "QUEUED", 1: "RUNNING", 2: "COMPLETE", 3: "ERROR",
            4: "CANCEL_REQUESTED", 5: "CANCEL_ACKNOWLEDGED", 6: "NEW_SCRIPT"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def schedule(start: datetime) -> list[str]:
    return [(start + timedelta(seconds=INTERVAL_SECONDS * index)).isoformat()
            for index in range(1, CHECK_COUNT + 1)]


def due_slots(check_times: list[str], now: datetime) -> list[int]:
    # Windows task triggers have second precision. Account for truncation of the
    # stored ISO timestamp; do not accidentally skip a just-fired timer.
    return [index for index, when in enumerate(check_times)
            if datetime.fromisoformat(when) <= now + timedelta(seconds=2)]


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def normalize_status(value) -> str:
    return STATUSES.get(value, "UNKNOWN") if isinstance(value, int) else str(value).upper()


def version_label(version: str) -> str:
    return "v" + version if version.isdigit() else version


def run_command(command: list[str], cwd: Path, log: Path, timeout: int, env=None) -> dict:
    # The Kaggle token belongs only in the monitor's authenticated API calls.
    # Never give it to frontend builds, browser processes, or application tests.
    env = dict(os.environ if env is None else env)
    env.pop("KAGGLE_API_TOKEN", None)
    env.pop("IML_KAGGLE_PAYLOAD", None)
    try:
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
                                    timeout=timeout, env=env)
        return {"status": "passed" if result.returncode == 0 else "failed",
                "exit_code": result.returncode, "log": str(log)}
    except subprocess.TimeoutExpired:
        return {"status": "timed_out", "log": str(log)}
    except OSError:
        return {"status": "blocked", "log": str(log)}


def download_results(owner: str, slug: str, version: str, destination: Path) -> dict:
    """Only bounded logs/JSON/test reports, not model weights or entire notebooks."""
    destination.mkdir(parents=True, exist_ok=True)
    token = ""
    downloaded = []
    for _ in range(10):
        response = call("kernels.KernelsApiService", "ListKernelSessionOutput", {
            "userName": owner, "kernelSlug": slug, "versionLabel": version_label(version),
            "pageSize": 100, "pageToken": token})
        if response.get("log"):
            (destination / "kernel.log").write_text(response["log"][:2_000_000], encoding="utf-8")
        for item in response.get("files", []):
            name = item.get("fileName", item.get("file_name", ""))
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            if relative.suffix not in {".json", ".jsonl", ".log", ".xml"} or \
                    "application-snapshot" in relative.parts or "pinned-research" in relative.parts:
                continue
            url = item.get("url", "")
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != "https" or not (parsed.hostname == "www.kaggleusercontent.com" or
                                                parsed.hostname == "storage.googleapis.com"):
                continue
            # Signed artifact URLs are never logged. No Authorization header is forwarded.
            with urllib.request.urlopen(url, timeout=90) as stream:
                data = stream.read(20_000_001)
            if len(data) > 20_000_000:
                raise RuntimeError("Artifact exceeds the bounded download size.")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            downloaded.append(name)
        token = response.get("nextPageToken", "")
        if not token:
            break
    return {"downloaded": downloaded}


def kaggle_check(job: dict, destination: Path) -> dict:
    response = call("kernels.KernelsApiService", "GetKernelSessionStatus", {
        "userName": job["owner"], "kernelSlug": job["slug"], "versionLabel": version_label(job["version"])})
    status = normalize_status(response.get("status", "QUEUED"))
    result = {"job": job["owner"] + "/" + job["slug"], "version": job["version"],
              "status": status, "checked_at": utcnow().isoformat()}
    if status == "RUNNING":
        try:
            text = read_progress({"userName": job["owner"], "kernelSlug": job["slug"],
                                  "versionLabel": version_label(job["version"]),
                                  "waitForLogsUrlSeconds": 1})
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "latest-progress.log").write_text(text, encoding="utf-8")
            digest = hashlib.sha256(text.encode()).hexdigest()
            result["log_snapshot_bytes"] = len(text.encode())
            result["log_changed_since_last_check"] = digest != job.get("last_log_sha256") if text else None
            job["last_log_sha256"] = digest
        except Exception as error:
            result["live_logs"] = "unavailable"
            result["live_log_error_type"] = type(error).__name__
    if status in {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED"} and not job.get("downloaded"):
        result.update(download_results(job["owner"], job["slug"], job["version"], destination))
        job["downloaded"] = (destination / "batch-status.json").exists() or \
                            (destination / "pilot-metadata.json").exists()
    summary = destination / "batch-status.json"
    if summary.exists():
        result["application_batch"] = json.loads(summary.read_text(encoding="utf-8"))
    pilot = destination / "pilot-metadata.json"
    if pilot.exists():
        result["pilot_status"] = json.loads(pilot.read_text(encoding="utf-8")).get("status")
    # A running status is not a proof of progress or success. Never restart a
    # job just because one poll found RUNNING/QUEUED or the API was unavailable.
    result["progress_scope"] = "Kaggle state; completed logs/rows verify work. No idle-session keep-alive."
    job["last_status"] = status
    return result


def check(state_path: Path, index: int | None = None) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    now = utcnow()
    if index is None:
        due = due_slots(state["check_times"], now)
        if not due:
            return {"status": "not_due"}
        index = due[-1]
    if not 0 <= index < CHECK_COUNT or str(index) in state["checks"]:
        return {"status": "already_checked_or_out_of_range"}
    # Do not continue an old monitor indefinitely after sleep/reboot.
    if now > datetime.fromisoformat(state["check_times"][-1]) + timedelta(minutes=25):
        return {"status": "expired"}
    destination = state_path.parent / f"check-{index + 1:02d}"
    destination.mkdir(parents=True, exist_ok=True)
    report = {"slot": index + 1, "started_at": now.isoformat(), "kaggle": []}
    for job in state["jobs"]:
        try:
            report["kaggle"].append(kaggle_check(job, state_path.parent / "kaggle-output" / job["slug"]))
        except Exception as error:
            report["kaggle"].append({"job": job["owner"] + "/" + job["slug"],
                                     "status": "check_failed", "error_type": type(error).__name__})
    python = str(ROOT / ".venv/Scripts/python.exe")
    report["backend"] = run_command(
        [python, "-m", "pytest", "tests", "-q"],
        ROOT / "backend", destination / "backend.log", 300)
    npm = str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "nodejs/npm.cmd")
    report["frontend"] = run_command([npm, "run", "check"], ROOT, destination / "frontend.log", 300)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "backend/src"))
    cases = state_path.parent / "initial-application/application-cases.json"
    report["live_api"] = run_command(
        [python, str(ROOT / "scripts/compression_research/application_matrix.py"), "--base-url",
         "http://127.0.0.1:8000", "--cases", str(cases), "--rotation", str(index),
         "--output", str(destination / "live-api")], ROOT, destination / "live-api.log", 300, env)
    cli = Path(os.environ["APPDATA"]) / "npm/playwright-cli.cmd"
    if cli.exists():
        session = f"iml-timer-{index + 1}"
        browser = run_command([str(cli), f"-s={session}", "open", "http://127.0.0.1:8080/compression",
                               "--browser=chrome"], destination, destination / "browser-open.log", 60)
        if browser["status"] == "passed":
            browser = run_command([str(cli), f"-s={session}", "run-code", "--filename=" +
                                   str(ROOT / "scripts/check_compression_browser.js")],
                                  destination, destination / "browser.log", 150)
            # CLI can return zero after a script error; require the actual result.
            output = (destination / "browser.log").read_text(encoding="utf-8")
            if '"page_errors":[]' not in output or '"candidate_unchanged":true' not in output:
                browser["status"] = "failed"
        run_command([str(cli), f"-s={session}", "close"], destination, destination / "browser-close.log", 60)
        report["browser"] = browser
    else:
        report["browser"] = {"status": "blocked", "reason": "Installed browser CLI not found"}
    report["finished_at"] = utcnow().isoformat()
    report["application_status"] = "passed" if all(report[key]["status"] == "passed" for key in
                                                 ("backend", "frontend", "live_api", "browser")) else "attention_required"
    state["checks"][str(index)] = report
    write_json(destination / "report.json", report)
    write_json(state_path, state)
    print(json.dumps(report, indent=2))
    return report


def run_schedule(state_path: Path) -> None:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    waiter = threading.Event()
    for index, when in enumerate(state["check_times"]):
        due = datetime.fromisoformat(when)
        delay = (due - utcnow()).total_seconds()
        if delay > 0:
            waiter.wait(delay)  # Real bounded timer in the detached worker, not agent polling.
        if utcnow() - due > timedelta(minutes=25):
            continue
        check(state_path, index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("initialize", "check", "run", "status", "track"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--index", type=int)
    parser.add_argument("--job", action="append", default=[])
    args = parser.parse_args()
    if args.action == "initialize":
        if args.state.exists():
            raise RuntimeError("Monitor state already exists; refusing to reset history.")
        start = utcnow()
        jobs = []
        for item in args.job:
            owner, slug, version = item.split("/")
            jobs.append({"owner": owner, "slug": slug, "version": version})
        args.state.parent.mkdir(parents=True, exist_ok=True)
        state = {"created_at": start.isoformat(), "interval_seconds": INTERVAL_SECONDS,
                 "check_count": CHECK_COUNT, "check_times": schedule(start), "jobs": jobs, "checks": {},
                 "requires": "Windows computer on/awake, internet, same signed-in user; no wake or idle evasion"}
        write_json(args.state, state)
        print(json.dumps(state, indent=2))
    elif args.action == "check":
        check(args.state, args.index)
    elif args.action == "status":
        state = json.loads(args.state.read_text(encoding="utf-8"))
        reports = [kaggle_check(job, args.state.parent / "kaggle-output" / job["slug"])
                   for job in state["jobs"]]
        write_json(args.state, state)
        print(json.dumps(reports, indent=2))
    elif args.action == "track":
        state = json.loads(args.state.read_text(encoding="utf-8"))
        for item in args.job:
            owner, slug, version = item.split("/")
            if not any(job["owner"] == owner and job["slug"] == slug for job in state["jobs"]):
                state["jobs"].append({"owner": owner, "slug": slug, "version": version})
        write_json(args.state, state)
        print(json.dumps(state["jobs"], indent=2))
    else:
        run_schedule(args.state)


if __name__ == "__main__":
    main()
