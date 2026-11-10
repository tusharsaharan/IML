"""run02: free Groq labeling (cheap 20b vs premium-proxy 120b), resumable.

Usage: GROQ_API_KEY=... python run02_label.py [--max-new 100] [--target 1200] [--sleep 4]
Re-run until it prints LABELING COMPLETE. Checkpoints every query.
Exit code 2 = more remaining (re-run me).

Protocol (frozen pre-grading, see DECISION_01): target = first 1200 queries
(all 75 real + 1125 aug). Gentle pace avoids 429 backoff spirals.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import CHEAP_MODEL, PREMIUM_MODEL, chat_once, load_jsonl, track  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--max-new", type=int, default=100, help="max new queries per invocation")
ap.add_argument("--target", type=int, default=1200, help="label first N queries only")
ap.add_argument("--sleep", type=float, default=10.0, help="steady pause between queries (avoids 429s)")
ap.add_argument("--sleep-inner", type=float, default=3.0, help="pause between cheap and premium call")
ap.add_argument("--max-tokens", type=int, default=160)
args = ap.parse_args()

t = track()
queries = load_jsonl(t / "queries.jsonl")[: args.target]
assert queries, "run run01_queries.py first"
out = t / "groq_labels.jsonl"
done = {r["id"] for r in load_jsonl(out)}
# drop any labels beyond target (from earlier 3000-plan runs)
print(f"target={len(queries)} done_in_target={len(done & {q['id'] for q in queries})} total_ckpt={len(done)}")

todo = [q for q in queries if q["id"] not in done][: args.max_new]
if not todo:
    print("LABELING COMPLETE")
    raise SystemExit(0)

with open(out, "a", encoding="utf-8") as fh:
    for k, q in enumerate(todo):
        c_text, c_use = chat_once(CHEAP_MODEL, q["text"], max_tokens=args.max_tokens)
        time.sleep(args.sleep_inner)
        p_text, p_use = chat_once(PREMIUM_MODEL, q["text"], max_tokens=args.max_tokens)
        fh.write(
            json.dumps(
                {"id": q["id"], "text": q["text"], "ref": q["ref"], "src": q["src"],
                 "cheap": c_text, "premium": p_text, "cheap_usage": c_use, "premium_usage": p_use,
                 "proxy": True, "cheap_model": CHEAP_MODEL, "premium_model": PREMIUM_MODEL},
                ensure_ascii=False,
            )
            + "\n"
        )
        fh.flush()
        if (k + 1) % 10 == 0:
            print(f"  +{k + 1}/{len(todo)} ...", flush=True)
        time.sleep(args.sleep)

remaining = len([q for q in queries if q["id"] not in done]) - len(todo)
print(f"chunk done. remaining_in_target={remaining}")
raise SystemExit(2 if remaining > 0 else 0)
