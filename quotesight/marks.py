"""The user's own highlights on PDF pages, each with a stance (support / refute / context).

Stored in <data_dir>/highlights.json, keyed to the PDF path so they survive re-indexing (paper ids can change).
They stay on this computer and are never sent to the LLM.
"""
import json
import os
import time

from . import config, core

STANCES = ("support", "refute", "context")
_PAPER_SQL = ("SELECT p.id, p.filename AS file, p.folder, p.path AS pdf, p.note, COALESCE(m.title, p.title) AS title, "
              "m.authors, COALESCE(m.year, p.year) AS year, COALESCE(m.journal, p.journal) AS journal, m.doi "
              "FROM papers p LEFT JOIN meta m ON m.path=p.path WHERE ")


def path():
    return config.get().data_dir / "highlights.json"


def load():
    try:
        return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(items):
    tmp = path().with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path())


def list_marks():
    con = core.connect()
    out = []
    for m in reversed(load()):
        row = con.execute(_PAPER_SQL + "p.path=?", (m.get("pdf"),)).fetchone()
        out.append(dict(m, paper=dict(row) if row else {"file": os.path.basename(m.get("pdf") or ""), "pdf": m.get("pdf")}))
    return out


def add(paper_id, page, text, stance):
    text = " ".join((text or "").split())
    if stance not in STANCES or len(text) < 8:
        raise ValueError("bad highlight")
    row = core.connect().execute(_PAPER_SQL + "p.id=?", (paper_id,)).fetchone()
    if not row:
        raise ValueError("paper not found")
    items = load()
    m = {"id": time.strftime("%Y%m%d-%H%M%S") + f"-{len(items)}", "time": time.time(), "pdf": row["pdf"],
         "page": int(page), "text": text, "stance": stance}
    items.append(m)
    _save(items)
    return dict(m, paper=dict(row))


def update(mid, stance):
    items = load()
    for m in items:
        if m["id"] == mid and stance in STANCES:
            m["stance"] = stance
            _save(items)
            return True
    return False


def delete(mid):
    items = load()
    keep = [m for m in items if m["id"] != mid]
    if len(keep) == len(items):
        return False
    _save(keep)
    return True
