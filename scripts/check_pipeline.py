"""Offline presentation rehearsal against the real endpoint, with disposable data."""
import json
import os
import tempfile
from pathlib import Path


def main():
    from fastapi.testclient import TestClient

    with tempfile.TemporaryDirectory(prefix="iml-demo-") as folder:
        os.environ["IML_MODE"] = "demo"
        os.environ["IML_DATABASE_PATH"] = str(Path(folder) / "demo.sqlite3")
        from gateway.core.config import get_settings
        get_settings.cache_clear()
        from gateway.app import app

        with TestClient(app) as client:
            rows = []
            for text in (
                "Yaar basically mera hostel ka wifi bahut slow chal raha hai",
                "How can I renew a library book?",
                "असाइनमेंट जमा करने की अंतिम तिथि कहाँ देख सकते हैं?",
            ):
                payload = {"text": text, "mode": "demo", "compression": {"method": "crf"}}
                cold = client.post("/api/v1/chat", json=payload)
                cold.raise_for_status()
                result = cold.json()
                assert result["answer_source"] == "authored-demo"
                assert result["cache"]["hit"] is False
                warm = client.post("/api/v1/chat", json=payload)
                warm.raise_for_status()
                assert warm.json()["cache"]["hit"] is True
                assert warm.json()["compression"] is None
                rows.append({"language": result["language"], "method": result["compression"]["method"],
                             "route": result["routing"]["selected_tier"], "repeat": "exact cache hit"})
            print(json.dumps({"status": "passed", "mode": "authored demo", "scenarios": rows}, indent=2))


if __name__ == "__main__":
    main()
