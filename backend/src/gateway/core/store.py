from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
create table if not exists requests (
  id integer primary key autoincrement,
  created_at text not null,
  text text not null,
  language text not null,
  result_json text not null
);
create table if not exists cache_entries (
  id integer primary key autoincrement,
  created_at text not null,
  question text not null,
  normalized text not null,
  answer text not null,
  language text not null,
  source text not null,
  embedding_json text
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def record_request(self, text: str, language: str, result: dict[str, Any]) -> int:
        with self.connect() as db:
            cur = db.execute(
                "insert into requests(created_at,text,language,result_json) values (?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), text, language, json.dumps(result, ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def list_requests(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "select id, created_at, text, language, result_json from requests order by id desc limit ?",
                (limit,),
            ).fetchall()
        return [{**dict(r), "result": json.loads(r["result_json"])} for r in rows]

    def put_cache(self, question: str, normalized: str, answer: str, language: str, source: str, embedding: list[float] | None = None) -> int:
        with self.connect() as db:
            cur = db.execute(
                "insert into cache_entries(created_at,question,normalized,answer,language,source,embedding_json) values (?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), question, normalized, answer, language, source, json.dumps(embedding) if embedding else None),
            )
            return int(cur.lastrowid)

    def list_cache(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "select id, created_at, question, normalized, answer, language, source, embedding_json from cache_entries order by id desc limit ?",
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["embedding"] = json.loads(item.pop("embedding_json") or "null")
            items.append(item)
        return items
