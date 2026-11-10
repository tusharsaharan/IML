"""Small explicit Kaggle batch client. Credentials come only from the environment.

No credential is embedded in notebooks or persisted by this module. POST calls
are deliberately not retried: a lost response must not create duplicate jobs.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

API = "https://api.kaggle.com/v1/"


def read_progress(payload: dict) -> str:
    """Read a small, time-bounded log snapshot; never keep a stream open overnight."""
    token = os.environ.get("KAGGLE_API_TOKEN")
    if not token:
        raise RuntimeError("KAGGLE_API_TOKEN is not configured.")
    request = urllib.request.Request(
        API + "kernels.KernelsApiService/GetKernelSessionLogsStream",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    chunks = []
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=5) as stream:
        while sum(map(len, chunks)) < 200_000 and time.monotonic() - started < 10:
            try:
                part = stream.read1(16384)
            except TimeoutError:
                break
            if not part:
                break
            chunks.append(part)
            if b"END_OF_LOG" in part:
                break
    return b"".join(chunks).decode("utf-8", errors="replace").replace(token, "[REDACTED]")


def call(service: str, operation: str, payload: dict) -> dict:
    token = os.environ.get("KAGGLE_API_TOKEN")
    if not token:
        raise RuntimeError("KAGGLE_API_TOKEN is not configured.")
    request = urllib.request.Request(
        API + service + "/" + operation,
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                 "User-Agent": "IML-compression-application-tests/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        # Do not print response bodies or request headers containing credentials.
        raise RuntimeError(f"Kaggle {operation} returned HTTP {error.code}.") from None
    except urllib.error.URLError:
        raise RuntimeError(f"Kaggle {operation} network request failed.") from None
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected Kaggle {operation} response.")
    return result


if __name__ == "__main__":
    import sys
    payload = json.loads(os.environ.get("IML_KAGGLE_PAYLOAD", "{}"))
    if sys.argv[2] == "GetKernelSessionLogsStream":
        print(read_progress(payload))
    else:
        print(json.dumps(call(sys.argv[1], sys.argv[2], payload), indent=2))
