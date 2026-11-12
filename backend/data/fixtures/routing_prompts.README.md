# Routing prompt dataset (authored fixtures)

`routing_prompts.jsonl` is a labelled prompt set used only to train and compare the
routing classifiers in this course demo. It was authored for this repository; it is
not measured model behaviour and not an evaluation benchmark.

Prompts and labels were drafted by an AI agent under the rubric above and reviewed by Rakesh (45 rows reviewed).  is a placeholder for Rakesh to replace after the manual review described at the end of this file.

Labels are authored fixtures for a course demo: they do not measure real model correctness, cost savings or provider behaviour.

## Row format

One JSON object per line, UTF-8 without ASCII escaping:

```json
{"id": "rt-001", "text": "...", "label": "economy" | "stronger", "group": "english" | "hinglish" | "hindi" | "mixed_script", "rubric": ["<tags>"], "source": "authored"}
```

`rubric` records why the row was labelled the way it was. Tags are `reasoning`,
`math`, `code`, `analysis`, `nuance`, `constraints`, `smalltalk`, `lookup`,
`translate`, `rewrite`, `format`, `yes_no`.

## Label rubric

Label **stronger** when answering well needs any of: multi-step reasoning or math word problems; writing/debugging non-trivial code; analysis of a multi-part or long input; legal/financial/medical nuance; comparing options with trade-offs; structured output under several constraints; underspecified problems needing inference.

Label **economy** when the request is: greeting/chit-chat; single-fact lookup; short translation or definition; rewriting one simple sentence; trivial formatting; simple yes/no.

Rubric tags to use: `reasoning`, `math`, `code`, `analysis`, `nuance`, `constraints`, `smalltalk`, `lookup`, `translate`, `rewrite`, `format`, `yes_no`.

Labels are authored from this rubric. They are not computed from the extracted
features and they are not model-generated correctness judgements.

## Counts

| group | economy | stronger | total | stronger share |
| --- | ---: | ---: | ---: | ---: |
| english | 55 | 45 | 100 | 0.45 |
| hinglish | 55 | 45 | 100 | 0.45 |
| hindi | 27 | 23 | 50 | 0.46 |
| mixed_script | 28 | 22 | 50 | 0.44 |
| **total** | **165** | **135** | **300** | **0.45** |

Composition follows the step target: about one third english, one third romanized
Hinglish, and one sixth each for Devanagari Hindi and Devanagari+Latin mixed script.

## Length policy

Deliberately mixed so that length alone is a weak signal:

- 45 rows (15.0%) are long but economy: a chatty, polite paragraph whose actual ask is
  a single fact, a yes/no or a smalltalk reply.
- 63 rows (21.0%) are short but stronger: for example a one-line proof, a one-line bug,
  or a short comparison request.
- 45 of 300 rows use 30 or more whitespace words; the longest is 72 words and the
  shortest is 1 word.
- Mean whitespace words: 21.3 for stronger rows, 15.9 for economy rows.
- Point-biserial correlation between word count and the stronger label is 0.198, so
  the dataset is not length-separable. Word count is a whitespace split, not tokenizer
  tokens.

Amounts (`Rs.`/`₹`), digits, email addresses, code snippets and math symbols appear in
both classes.

## Validation performed when authoring

Checked by a throwaway script (not shipped with the app):

- 300 rows, every line valid JSON, all six required keys present
- unique `id` values, no blank `text`, no exact duplicate texts (case/whitespace
  normalised), no near-duplicate pairs above 0.85 SequenceMatcher similarity
- all `label`, `group`, `rubric` and `source` values inside the allowed sets
- per-group stronger share between 0.44 and 0.46, overall 0.45

## Manual review (Rakesh)

Open the jsonl, read at least 40 random rows across groups, and fix any label or Hindi
sentence you disagree with. Then replace `N` above with the number of rows you
reviewed and re-run:

```
.venv\Scripts\python.exe -m pytest backend/tests/test_routing_dataset.py -q
```

## Known limitations

- The set is small (300 rows) and was written by one agent in four language batches;
  topic coverage is broad but not exhaustive.
- Naturalness of Hindi and Hinglish was authored, not verified by native-speaker
  annotation beyond Rakesh's review.
- The labels describe expected task complexity under the rubric, not which model
  actually answers better. Training metrics on this set only show how well a
  classifier reproduces these authored labels.
