"""run02b: refill rows whose cheap/premium content came back empty.

Re-calls ONLY the empty side with a bigger budget (320 tokens). In-place
update of groq_labels.jsonl, checkpointed every 20 rows. Re-runnable.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import CHEAP_MODEL, PREMIUM_MODEL, chat_once, load_jsonl, track  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--max-new", type=int, default=200)
ap.add_argument("--sleep", type=float, default=8.0)
ap.add_argument("--sleep-inner", type=float, default=2.0)
args = ap.parse_args()

t = track()
path = t / "groq_labels.jsonl"
rows = load_jsonl(path)
todo = [r for r in rows if not r["cheap"].strip() or not r["premium"].strip()][: args.max_new]
print(f"empty-sided rows remaining: {len([r for r in rows if not r['cheap'].strip() or not r['premium'].strip()])}, doing {len(todo)}")
if not todo:
    print("REFILL COMPLETE")
    raise SystemExit(0)

by_id = {r["id"]: r for r in rows}
for k, r in enumerate(todo):
    if not r["cheap"].strip():
        c_text, c_use = chat_once(CHEAP_MODEL, r["text"], max_tokens=224)
        r["cheap"], r["cheap_usage"] = c_text, c_use
        time.sleep(args.sleep_inner)
    if not r["premium"].strip():
        p_text, p_use = chat_once(PREMIUM_MODEL, r["text"], max_tokens=224)
        r["premium"], r["premium_usage"] = p_text, p_use
    if (k + 1) % 20 == 0:
        with open(path, "w", encoding="utf-8") as fh:
            for x in rows:
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"  +{k + 1}/{len(todo)} checkpointed", flush=True)
    time.sleep(args.sleep)

with open(path, "w", encoding="utf-8") as fh:
    for x in rows:
        fh.write(json.dumps(x, ensure_ascii=False) + "\n")
left = len([r for r in rows if not r["cheap"].strip() or not r["premium"].strip()])
print(f"refill chunk done. empty-sided remaining={left}")
raise SystemExit(2 if left > 0 else 0)
