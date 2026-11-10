"""Private CPU research pilot; not an application compressor or acceptance study.

The launcher embeds the existing source manifest as RESEARCH_MANIFEST. Only main()
downloads dependencies/models, inside a disposable Kaggle batch session. Importing
this file is offline. Authored literal cases are not semantic-quality benchmarks.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import re
import string
import subprocess
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

RESEARCH_COMMIT = "fa1258135268ca2650170a3f358975ce49169290"
LLMLINGUA_COMMIT = "01b9e9481d7395e1e83a48df4a062b11f6304325"
COMPRESSOR_MODEL = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
COMPRESSOR_REVISION = "5f0c82792b7ea14c6484e015b6a072009496b7f2"
READER_MODEL = "deepset/roberta-base-squad2"
READER_REVISION = "adc3b06f79f797d1c575d5479d6f5efe54a9e3b4"
SQUAD_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json"
XQUAD_COMMIT = "7d30520c717524000f0d9d2f9c10a069acd9d285"
XQUAD_URL = f"https://raw.githubusercontent.com/google-deepmind/xquad/{XQUAD_COMMIT}/xquad.hi.json"
RATES = (0.3, 0.5, 0.7, 0.9)
SEED = 20261109


def literal_checks(original: str, candidate: str, phrases: list[str]) -> list[dict]:
    """Post-run occurrence observation; phrases are never fed to compressors."""
    if any(not phrase or phrase not in original for phrase in phrases):
        raise ValueError("Every literal must exist in the source.")
    return [{"phrase": phrase, "source_count": original.count(phrase),
             "candidate_count": candidate.count(phrase),
             "survived": candidate.count(phrase) >= original.count(phrase)}
            for phrase in phrases]


def normalize_answer(text: str) -> str:
    lowered = text.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(re.sub(r"\b(a|an|the)\b", " ", lowered).split())


def answer_scores(prediction: str, answers: list[str]) -> dict:
    """Standard English SQuAD EM/F1, not a multilingual chat-quality score."""
    pred = normalize_answer(prediction).split()
    values = []
    for answer in answers:
        gold = normalize_answer(answer).split()
        overlap = sum((Counter(pred) & Counter(gold)).values())
        if not pred or not gold:
            f1 = float(pred == gold)
        else:
            f1 = 2 * overlap / (len(pred) + len(gold))
        values.append((float(pred == gold), f1))
    return {"em": max((v[0] for v in values), default=0.0),
            "f1": max((v[1] for v in values), default=0.0)}


def observed_row(case: dict, method: str, actual_method: str, rate: float | None,
                 output: str, counter, elapsed_ms: float) -> dict:
    original = case["text"]
    checks = literal_checks(original, output, case.get("phrases", []))
    fallback = any(not check["survived"] for check in checks)
    final = original if fallback else output
    original_tokens = counter.count(original)
    candidate_tokens = counter.count(output)
    target = math.floor(original_tokens * rate) if rate is not None else None
    return {"id": case["id"], "language": case["language"], "kind": case["kind"],
            "requested_method": method, "actual_method": actual_method,
            "requested_keep_rate": rate, "budget_tunable": method == "llmlingua2_raw",
            "original": original, "candidate": output, "guarded_final": final,
            "original_tokens": original_tokens, "candidate_tokens": candidate_tokens,
            "guarded_tokens": counter.count(final),
            "achieved_keep_rate": candidate_tokens / max(1, original_tokens),
            "target_tokens": target, "budget_met": candidate_tokens <= target if target is not None else None,
            "empty_candidate": not output.strip(), "expanded": candidate_tokens > original_tokens,
            "literal_checks": checks, "protection_fallback": fallback,
            "elapsed_ms": elapsed_ms, "qa": None, "error": None}


def authored_cases() -> list[dict]:
    specs = {
        "en": [
            ("Hello, please send the invoice to user@example.com, not sales@example.com.", ["user@example.com", "not"]),
            ("Please never cancel order AB-123. Refund only INR 250 on 2026-11-12.", ["never", "AB-123", "INR 250", "2026-11-12"]),
            ("The password must not be included. Share only the public URL https://example.org/help.", ["not", "https://example.org/help"]),
            ("The service is slow, really really slow. Keep retry_limit=3 and timeout=45 unchanged.", ["retry_limit=3", "timeout=45"]),
            ("Notify Aman and Tushar separately. Aman owns insights; Tushar owns compression.", ["Aman", "Tushar", "insights", "compression"]),
            ("Output JSON only. Do not include markdown. The two required fields are name and amount.", ["JSON", "not", "name", "amount"]),
        ],
        "hinglish": [
            ("yaar matlab invoice user@example.com par bhejo, sales@example.com par nahi.", ["user@example.com", "nahi"]),
            ("bhai order AB-123 kabhi cancel mat karna. Sirf INR 250 refund karo 2026-11-12 ko.", ["mat", "AB-123", "INR 250", "2026-11-12"]),
            ("please password share nahi karna, bas https://example.org/help wala public link bhejna.", ["nahi", "https://example.org/help"]),
            ("yaar service slow slow slow hai, retry_limit=3 aur timeout=45 ko change mat karna.", ["retry_limit=3", "timeout=45", "mat"]),
            ("Aman insights dekhega aur Tushar compression. Aman aur Tushar ko alag notify karo.", ["Aman", "Tushar", "insights", "compression"]),
            ("sirf JSON output dena, markdown nahi. name aur amount dono fields chahiye.", ["JSON", "nahi", "name", "amount"]),
        ],
        "hi": [
            ("कृपया चालान रीना को भेजें, मोहन को नहीं।", ["रीना", "मोहन", "नहीं"]),
            ("यह आदेश कभी रद्द मत करना। केवल दो सौ पचास रुपये वापस करें।", ["मत", "दो सौ पचास"]),
            ("गुप्त पासवर्ड साझा नहीं करना। केवल सार्वजनिक जानकारी भेजना।", ["नहीं", "सार्वजनिक"]),
            ("सेवा बहुत धीमी है। समय सीमा पैंतालीस सेकंड रखें, इसे बदलना मत।", ["पैंतालीस", "मत"]),
            ("अमन और तुषार को अलग सूचना दें। अमन रिपोर्ट और तुषार संपीड़न संभालेंगे।", ["अमन", "तुषार", "रिपोर्ट", "संपीड़न"]),
            ("केवल दो क्षेत्र चाहिए: नाम और राशि। कोई अतिरिक्त टिप्पणी नहीं चाहिए।", ["नाम", "राशि", "नहीं"]),
        ],
        "mixed": [
            ("कृपया invoice user@example.com पर भेजें, sales@example.com पर नहीं।", ["user@example.com", "नहीं"]),
            ("order AB-123 cancel मत करना। केवल INR 250 refund करें 2026-11-12 को।", ["AB-123", "मत", "INR 250", "2026-11-12"]),
            ("password share नहीं करना, public URL https://example.org/help भेजें।", ["नहीं", "https://example.org/help"]),
            ("wifi slow slow है। retry_limit=3 और timeout=45 को बदलना मत।", ["retry_limit=3", "timeout=45", "मत"]),
            ("Aman insights और Tushar compression संभालेंगे। Aman और Tushar को अलग notify करें।", ["Aman", "Tushar", "insights", "compression"]),
            ("केवल JSON दें, markdown नहीं। name और amount दोनों fields चाहिए।", ["JSON", "नहीं", "name", "amount"]),
        ],
    }
    return [{"id": f"authored-{language}-{index}", "language": language,
             "kind": "authored_literal_smoke", "text": text, "phrases": phrases}
            for language, items in specs.items() for index, (text, phrases) in enumerate(items)]


def fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def verified_source_data(data: bytes, expected_sha256: str, text_file: bool) -> bytes:
    """Accept exact manifest bytes or a verified text newline-only conversion.

    The Windows import manifest hashes CRLF copies; GitHub raw serves LF. Never
    weaken content verification, rewrite the manifest, or normalize binary weights.
    """
    variants = [data]
    if text_file:
        lf = data.replace(b"\r\n", b"\n")
        variants += [lf, lf.replace(b"\n", b"\r\n")]
    for variant in variants:
        if hashlib.sha256(variant).hexdigest() == expected_sha256:
            return variant
    raise ValueError("Research fingerprint mismatch; not a newline-only difference.")


def import_research(root: Path, manifest: dict) -> dict:
    if manifest["commit"] != RESEARCH_COMMIT:
        raise ValueError("Research pin does not match the approved manifest.")
    selected = []
    for item in manifest["files"]:
        path = item["source"]
        if path.startswith(("backend/src/gateway/", "backend/data/models/crf_compressor.pkl",
                            "backend/data/tfidf/hinglish_idf.json")):
            if "/m3_conformal/" in path or "/m4_router/" in path or "/m12_semantic/" in path:
                continue
            data = fetch_bytes(f"https://raw.githubusercontent.com/tusharsaharan/Research/{RESEARCH_COMMIT}/{path}")
            raw_digest = hashlib.sha256(data).hexdigest()
            data = verified_source_data(data, item["sha256"], Path(path).suffix in {".py", ".json"})
            digest = hashlib.sha256(data).hexdigest()
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            selected.append({"path": path, "sha256": digest, "github_raw_sha256": raw_digest,
                             "newline_conversion_only": digest != raw_digest})
    return {"commit": RESEARCH_COMMIT, "files": selected}


def squad_cases() -> tuple[list[dict], dict]:
    data = fetch_bytes(SQUAD_URL)
    corpus = json.loads(data)
    paragraphs = [p for article in corpus["data"] for p in article["paragraphs"]]
    # Disjoint article halves: the pilot uses only the first half. Later evaluation
    # must not tune on the reserved articles; this does not imply unseen reader data.
    articles = corpus["data"][:len(corpus["data"]) // 2]
    eligible = [(a["title"], p, q) for a in articles for p in a["paragraphs"]
                for q in p["qas"] if q["answers"] and 400 <= len(p["context"]) <= 1800]
    rng = random.Random(SEED)
    rng.shuffle(eligible)
    cases = []
    seen = set()
    for title, passage, question in eligible:
        if passage["context"] in seen:
            continue
        seen.add(passage["context"])
        # Distractors selected without looking for/receiving the gold answer.
        pool = [p["context"] for p in paragraphs if p["context"] != passage["context"]
                and 250 <= len(p["context"]) <= 900]
        contexts = [passage["context"], *rng.sample(pool, 2)]
        rng.shuffle(contexts)
        cases.append({"id": question["id"], "language": "en", "kind": "squad_dev_pilot",
                      "title": title, "text": "\n\n".join(contexts), "question": question["question"],
                      "answers": [a["text"] for a in question["answers"]], "phrases": []})
        if len(cases) == 32:
            break
    return cases, {"url": SQUAD_URL, "sha256": hashlib.sha256(data).hexdigest(),
                   "seed": SEED, "count": len(cases), "license": "CC BY-SA 4.0",
                   "selection": "first-half articles, shuffled, one question per unique paragraph",
                   "gold_given_to_compressor": False,
                   "reader_test_contamination": "SQuAD reader; dev familiarity is not ruled out"}


def hindi_cases() -> tuple[list[dict], dict]:
    data = fetch_bytes(XQUAD_URL)
    corpus = json.loads(data)
    items = [(p, q) for article in corpus["data"] for p in article["paragraphs"] for q in p["qas"]]
    random.Random(SEED).shuffle(items)
    cases, seen = [], set()
    for passage, question in items:
        if passage["context"] in seen:
            continue
        seen.add(passage["context"])
        cases.append({"id": "xquad-hi-" + question["id"], "language": "hi", "kind": "xquad_hi_pilot",
                      "text": passage["context"], "question": question["question"], "phrases": [],
                      "answers": [answer["text"] for answer in question["answers"]]})
        if len(cases) == 32:
            break
    return cases, {"url": XQUAD_URL, "commit": XQUAD_COMMIT, "sha256": hashlib.sha256(data).hexdigest(),
                   "count": len(cases), "license": "CC BY-SA 4.0",
                   "scoring": "answer-string survival only; not Hindi downstream correctness",
                   "gold_given_to_compressor": False}


def main() -> None:
    os.environ.update(CUDA_VISIBLE_DEVICES="", HF_HUB_DISABLE_TELEMETRY="1", USE_TF="0",
                      TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    output = Path("/kaggle/working")
    if not output.is_dir():
        raise RuntimeError("Run main only in a Kaggle evaluation session.")
    import resource
    manifest = globals().get("RESEARCH_MANIFEST")
    if not isinstance(manifest, dict):
        raise RuntimeError("The launcher must embed the existing source manifest.")
    started = time.perf_counter()
    metadata = {"kind": "kaggle_cpu_pilot", "integration_approved": False,
                "python": sys.version, "platform": platform.platform(), "cpu_count": os.cpu_count(),
                "threads": 4, "rates": RATES, "seed": SEED, "errors": [],
                "limitations": ["24 authored cases measure literal survival, not semantic equivalence.",
                                "English extractive QA is not Hinglish/Hindi chat correctness.",
                                "Pilot results cannot authorize integration or universal best claims.",
                                "Baseline decisions are fixed, not matched-rate tuned.",
                                "Timings are serial warm calls, not provider/API latency."]}
    rows = []

    def save() -> None:
        metadata["elapsed_seconds"] = time.perf_counter() - started
        metadata["process_peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        (output / "pilot-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        (output / "pilot-rows.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                        "transformers==4.57.6", "sklearn-crfsuite==0.5.0", "tiktoken==0.14.0",
                        "pydantic>=2,<3", "httpx>=0.27,<1", "tenacity>=8,<10", "accelerate>=1,<2",
                        f"https://github.com/microsoft/LLMLingua/archive/{LLMLINGUA_COMMIT}.zip"],
                       check=True, timeout=900)
        root = output / "pinned-research"
        metadata["research"] = import_research(root, manifest)
        sys.path.insert(0, str(root / "backend/src"))
        import nltk
        import torch
        from gateway.modules.m2_compressor.compressor import Compressor
        from gateway.modules.m2_compressor.crf_tagger import CRFTagger
        from gateway.tokenizer import TokenCounter
        from llmlingua import PromptCompressor
        from transformers import AutoModelForQuestionAnswering, AutoTokenizer, pipeline

        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
        nltk.download("punkt_tab", quiet=True, raise_on_error=True)
        counter = TokenCounter()
        if counter.backend != "tiktoken_cl100k_base":
            raise RuntimeError("Reference tokenizer failed; do not silently compare whitespace budgets.")
        metadata["tokenizer"] = counter.backend
        metadata["token_counts_are_billing"] = False
        metadata["packages"] = {name: importlib.metadata.version(name) for name in
                                ("torch", "transformers", "llmlingua", "sklearn-crfsuite", "tiktoken")}
        baseline = Compressor(counter, use_crf=True,
                              crf_model_path=root / "backend/data/models/crf_compressor.pkl",
                              tfidf_path=root / "backend/data/tfidf/hinglish_idf.json")
        if baseline._linguistic is None:
            raise RuntimeError("CRF initialization failed; baseline must not silently degrade.")

        class Observer(CRFTagger):
            succeeded = False

            def predict(self, tokens):
                labels = super().predict(tokens)
                self.succeeded = True
                return labels

        previous = baseline._linguistic._tagger
        observer = Observer(previous.model_path, previous.idf_map)
        baseline._linguistic._tagger = observer
        load_started = time.perf_counter()
        learned = PromptCompressor(model_name=COMPRESSOR_MODEL, device_map="cpu", use_llmlingua2=True,
                                   model_config={"revision": COMPRESSOR_REVISION, "trust_remote_code": False})
        metadata["learned_model"] = {"id": COMPRESSOR_MODEL, "revision": COMPRESSOR_REVISION,
                                     "source_commit": LLMLINGUA_COMMIT,
                                     "load_seconds": time.perf_counter() - load_started,
                                     "mode": "raw unmasked, no forced literals, context filter disabled"}
        learned.compress_prompt("A CPU warmup prompt containing a useful fact.", rate=0.5,
                                use_context_level_filter=False)
        qa_cases, metadata["dataset"] = squad_cases()
        hi_cases, metadata["hindi_dataset"] = hindi_cases()
        cases = authored_cases() + qa_cases + hi_cases
        (output / "pilot-cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        for case in cases:
            for method, rate in [("original", None), ("heuristic", None), ("crf", None),
                                 *[("llmlingua2_raw", rate) for rate in RATES]]:
                tick = time.perf_counter()
                try:
                    if method == "original":
                        text, actual = case["text"], "original"
                    elif method == "heuristic":
                        result = baseline.compress_heuristic(case["text"])
                        text, actual = result.compressed, result.method
                    elif method == "crf":
                        observer.succeeded = False
                        result = baseline.compress_crf(case["text"])
                        text, actual = result.compressed, result.method
                        if not observer.succeeded:
                            actual = "heuristic_or_prepass_without_crf_prediction"
                    else:
                        result = learned.compress_prompt(case["text"], rate=rate,
                                                         use_context_level_filter=False)
                        text, actual = result["compressed_prompt"], "llmlingua2_raw"
                    row = observed_row(case, method, actual, rate, text, counter,
                                       (time.perf_counter() - tick) * 1000)
                    if case["kind"] == "xquad_hi_pilot":
                        row["answer_string_survival"] = any(answer in text for answer in case["answers"])
                    rows.append(row)
                except Exception as error:
                    rows.append({"id": case["id"], "language": case["language"], "kind": case["kind"],
                                 "requested_method": method, "requested_keep_rate": rate,
                                 "error": f"{type(error).__name__}: {error}"})
            save()
            print(f"Compressed {case['id']}: {len(rows)} rows", flush=True)

        load_started = time.perf_counter()
        reader = pipeline("question-answering",
                          model=AutoModelForQuestionAnswering.from_pretrained(
                              READER_MODEL, revision=READER_REVISION, trust_remote_code=False, use_safetensors=True),
                          tokenizer=AutoTokenizer.from_pretrained(READER_MODEL, revision=READER_REVISION,
                                                                  trust_remote_code=False), device=-1)
        metadata["reader"] = {"id": READER_MODEL, "revision": READER_REVISION,
                              "load_seconds": time.perf_counter() - load_started,
                              "kind": "English extractive QA, no paid endpoint"}
        lookup = {case["id"]: case for case in qa_cases}
        for row in rows:
            if row.get("error") or row["kind"] != "squad_dev_pilot":
                continue
            case = lookup[row["id"]]
            try:
                prediction = reader(question=case["question"], context=row["candidate"] or " ",
                                    max_seq_len=384, doc_stride=128)["answer"] if row["candidate"].strip() else ""
                row["qa"] = {"prediction": prediction, **answer_scores(prediction, case["answers"])}
            except Exception as error:
                row["qa"] = {"error": f"{type(error).__name__}: {error}"}
            save()
        no_context = []
        for case in qa_cases:
            prediction = reader(question=case["question"], context="No supporting context is available.")["answer"]
            no_context.append({"id": case["id"], "prediction": prediction,
                               **answer_scores(prediction, case["answers"])})
        (output / "no-context-control.json").write_text(json.dumps(no_context, indent=2), encoding="utf-8")
        groups = defaultdict(list)
        for row in rows:
            groups[(row["kind"], row["language"], row["requested_method"], row["requested_keep_rate"])].append(row)
        summary = []
        for key, values in groups.items():
            good = [row for row in values if not row.get("error")]
            qa = [row["qa"] for row in good if row.get("qa") and "em" in row["qa"]]
            summary.append({"kind": key[0], "language": key[1], "method": key[2], "rate": key[3],
                            "attempts": len(values), "compression_errors": len(values) - len(good),
                            "qa_errors": sum(bool(row.get("qa", {}).get("error")) for row in good if row.get("qa")),
                            "mean_achieved_keep_rate": sum(r["achieved_keep_rate"] for r in good) / max(1, len(good)),
                            "guard_fallbacks": sum(r["protection_fallback"] for r in good),
                            "empty_candidates": sum(r["empty_candidate"] for r in good),
                            "mean_em": sum(q["em"] for q in qa) / len(qa) if qa else None,
                            "mean_f1": sum(q["f1"] for q in qa) / len(qa) if qa else None,
                            "qa_count": len(qa)})
        (output / "pilot-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        metadata["status"] = "complete"
    except Exception as error:
        metadata["status"] = "failed"
        metadata["errors"].append(f"{type(error).__name__}: {error}")
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
