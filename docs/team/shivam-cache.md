# Shivam — Memory & Cache

## Goal
Build an answer-reuse workspace that can return an existing response for repeated or similar questions.

## Own
- Frontend: `src/features/cache/`
- Backend: `backend/src/gateway/features/cache/`
- Tests: `backend/tests/test_cache*.py`

## Build
1. Implement exact cache lookup using normalized text and SQLite storage.
2. Add semantic lookup over a small curated FAQ set using imported embedding/hashing utilities or a lightweight local similarity method.
3. Return hit type, similarity score, matched question, answer and cache metadata.
4. Add cache management endpoints/actions: list entries, clear or delete an entry, and seed demo FAQs.
5. Show counters: total lookups, exact hits, semantic hits and misses.
6. Add safeguards in the UI/API note for near-matches: display similarity and the matched question.

## Demo cases
- Exact repeat of a cached support question.
- Hinglish paraphrase of a cached English FAQ.
- A request with different details that should not be reused.

## ML/course angle
- Similarity search / nearest-neighbour style retrieval.
- Threshold selection and false-match analysis on a small labelled query set.

## Done when
- `/api/v1/cache/lookup` distinguishes exact, semantic and miss cases.
- The page shows matched entries, similarity and cache controls.
- Targeted tests cover normalization, exact hits and a semantic-threshold case.