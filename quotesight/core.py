"""Core of QuoteSight: scan the library, extract PDF text, chunk it, index it (SQLite FTS5 plus
embedding vectors) and search it.

The library is only read. Everything written goes to the data folder set in the config.
"""
import hashlib
import os
import re
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutTimeout
from pathlib import Path

from . import config

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers(
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  folder TEXT, filename TEXT, title TEXT, year TEXT, journal TEXT, note TEXT,
  mtime REAL, size INTEGER, pages INTEGER, pdf_type TEXT, ocr_pages TEXT,
  status TEXT, error TEXT, indexed_at REAL, fp TEXT, dup_of INTEGER
);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY,
  paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  page INTEGER, ord INTEGER, is_ref INTEGER DEFAULT 0, text TEXT
);
CREATE INDEX IF NOT EXISTS chunks_paper ON chunks(paper_id);
CREATE TABLE IF NOT EXISTS vecs(
  chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
  v BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS meta(
  path TEXT PRIMARY KEY, doi TEXT, title TEXT, authors TEXT, journal TEXT, year TEXT,
  source TEXT, checked_at REAL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text, content='chunks', content_rowid='id', tokenize='porter unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
"""


def connect():
    con = sqlite3.connect(str(config.get().db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


# ---------------------------------------------------------------- chunking

REFS_RE = re.compile(
    r"^\s*#*\s*\**\s*(references( cited)?|literature cited|bibliography|reference list)\s*\**\s*:?\s*$", re.I)
VOL_PAGES_RE = re.compile(r"\b\d{1,4}\s*(\(\d{1,4}\))?\s*[,:]\s*\d{1,6}\s*[–-]\s*\d{1,6}\b")
AUTHOR_RE = re.compile(r"\b[A-Z][A-Za-z'\-]+,\s+(?:[A-Z]\.\s?){1,3}[,.&]")


def looks_like_refs(text):
    """A reference-list chunk: many 'vol, pages' or 'Surname, A.B.,' patterns."""
    return len(VOL_PAGES_RE.findall(text)) >= 3 or len(AUTHOR_RE.findall(text)) >= 8


def chash(text):
    return re.sub(r"[^a-z]", "", text.lower())[:300]


def clean(text):
    text = text.replace("\xa0", " ").replace("­", "")
    return re.sub(r"-\n(?=[a-z])", "", text)


def chunk_page(md, in_refs, chunk_words, max_words):
    """Split one page of markdown into chunks of about chunk_words. Returns (chunks, in_refs)."""
    paras, chunks, buf, buf_ref = [], [], [], in_refs
    for para in re.split(r"\n\s*\n", clean(md)):
        para = para.strip()
        if not para:
            continue
        if REFS_RE.match(para.splitlines()[0]):
            in_refs = True
        paras.append((re.sub(r"\s+", " ", para), in_refs))

    def flush():
        if buf:
            words = " ".join(buf).split()
            if len(words) > max_words:
                for i in range(0, len(words), chunk_words):
                    piece = words[max(0, i - 30): i + chunk_words]
                    if piece:
                        chunks.append((" ".join(piece), buf_ref))
            else:
                chunks.append((" ".join(words), buf_ref))
            buf.clear()

    for para, ref in paras:
        if ref != buf_ref:
            flush()
            buf_ref = ref
        buf.append(para)
        if sum(len(p.split()) for p in buf) >= chunk_words:
            flush()
    flush()
    chunks = [(c, r or looks_like_refs(c)) for c, r in chunks if len(c.split()) >= 8 and c.count("....") < 3]
    return chunks, in_refs


def extract(path, chunk_words=300, max_words=450):
    """Runs in a worker process. Returns page chunks and the text/scan classification."""
    import pdf_inspector as p

    try:
        res = p.extract_pages_markdown(path)
        in_refs, out = False, []
        for pg in res.pages:
            chunks, in_refs = chunk_page(pg.markdown or "", in_refs, chunk_words, max_words)
            out.extend((pg.page + 1, i, c, int(r)) for i, (c, r) in enumerate(chunks))
        ocr = [n + 1 for n in (res.pages_needing_ocr or [])]
        n_pages = len(res.pages)
        pdf_type = "scanned" if n_pages and len(ocr) >= 0.5 * n_pages else ("mixed" if ocr else "text")
        fp = hashlib.sha1(" ".join(c for _, _, c, _ in out[:3]).encode()).hexdigest() if out else None
        return {"ok": True, "chunks": out, "fp": fp, "pages": n_pages, "ocr": ocr, "pdf_type": pdf_type}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- library scan

def topic_of(path, root):
    cfg = config.get()
    if cfg["library"]["topics"] != "subfolder":
        return root.name
    rel = Path(path).relative_to(root)
    return rel.parts[0] if len(rel.parts) > 1 else root.name


def scan_library():
    """Return {pdf_path: topic} for every PDF under the configured roots."""
    cfg = config.get()
    exclude = set(cfg["library"]["exclude"])
    pattern = re.compile(cfg["library"]["topic_pattern"]) if cfg["library"]["topic_pattern"] else None
    found = {}
    for root in cfg.roots:
        if not root.is_dir():
            continue
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if x not in exclude and not x.startswith(".")]
            for n in names:
                if n.lower().endswith(".pdf"):
                    full = str(Path(d) / n)
                    topic = topic_of(full, root)
                    if pattern and not pattern.search(topic):
                        continue
                    found[full] = topic
    return found


def guess_from_filename(fn):
    stem = re.sub(r"\.pdf$", "", fn, flags=re.I)
    parts = stem.split("_")
    year = re.search(r"(19|20)\d{2}", parts[0])
    title = parts[-1] if len(parts) >= 3 else None
    return (year.group(0) if year else None), title


# ---------------------------------------------------------------- update

def update(workers=None, timeout=180, log=print, only=None, embed_after=True, meta_after=True):
    """Index new or changed PDFs, drop deleted ones, then embed and fetch metadata."""
    cfg = config.get()
    workers = workers or cfg["index"]["workers"]
    cw, mw = cfg["index"]["chunk_words"], cfg["index"]["max_words"]
    con = connect()
    found = scan_library()
    if only:
        only = {str(Path(o).resolve()) for o in only}
        found = {p: f for p, f in found.items() if p in only}
    known = {r["path"]: r for r in con.execute("SELECT id, path, mtime, size, status FROM papers")}

    removed = 0
    if not only:
        for path, row in known.items():
            if path not in found:
                con.execute("DELETE FROM papers WHERE id=?", (row["id"],))
                removed += 1

    todo = []
    for path in found:
        st = os.stat(path)
        row = known.get(path)
        orphan = row and row["status"] == "duplicate" and not con.execute(
            "SELECT 1 FROM papers WHERE id=(SELECT dup_of FROM papers WHERE path=?)", (path,)).fetchone()
        if row and not orphan and row["mtime"] == st.st_mtime and row["size"] == st.st_size \
                and row["status"] != "error":
            continue
        todo.append(path)

    notes = {}
    for path, folder in found.items():
        con.execute("UPDATE papers SET folder=? WHERE path=?", (folder, path))
    con.commit()

    hash_owner = {}
    skip = set(todo)
    for r in con.execute("SELECT c.paper_id, c.text, p.path FROM chunks c JOIN papers p ON p.id=c.paper_id"):
        if r["path"] not in skip:
            hash_owner.setdefault(chash(r["text"]), set()).add(r["paper_id"])

    def find_dup(chunks):
        hs = {chash(c) for _, _, c, _ in chunks if len(c) > 200}
        if len(hs) < 3:
            return None
        counts = {}
        for h in hs:
            for pid in hash_owner.get(h, ()):
                counts[pid] = counts.get(pid, 0) + 1
        best = max(counts.items(), key=lambda x: x[1], default=None)
        return best[0] if best and best[1] >= 0.5 * len(hs) else None

    log(f"{len(found)} PDFs in library, {len(todo)} to index, {removed} removed")
    done = errors = 0
    t0 = time.time()
    if todo:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {path: ex.submit(extract, path, cw, mw) for path in todo}
            for path, fut in futs.items():
                try:
                    res = fut.result(timeout=timeout)
                except FutTimeout:
                    res = {"ok": False, "error": "timeout"}
                except Exception as e:
                    res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                st = os.stat(path)
                fn = os.path.basename(path)
                meta = notes.get(fn, {})
                fy, ft = guess_from_filename(fn)
                title = meta.get("title") or ft or re.sub(r"\.pdf$", "", fn, flags=re.I)
                con.execute("DELETE FROM papers WHERE path=?", (path,))
                if res["ok"]:
                    dup = find_dup(res["chunks"]) if res["chunks"] else None
                    status = "duplicate" if dup else ("ok" if res["chunks"] else "empty")
                    cur = con.execute(
                        "INSERT INTO papers(path, folder, filename, title, year, journal, note, mtime, size, pages, "
                        "pdf_type, ocr_pages, status, indexed_at, fp, dup_of) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (path, found[path], fn, title, meta.get("year") or fy, meta.get("journal"), meta.get("note"),
                         st.st_mtime, st.st_size, res["pages"], res["pdf_type"], ",".join(map(str, res["ocr"])),
                         status, time.time(), res["fp"], dup))
                    pid = cur.lastrowid
                    if not dup:
                        con.executemany("INSERT INTO chunks(paper_id, page, ord, is_ref, text) VALUES (?,?,?,?,?)",
                                        [(pid, pg, o, r, c) for pg, o, c, r in res["chunks"]])
                        for _, _, c, _ in res["chunks"]:
                            hash_owner.setdefault(chash(c), set()).add(pid)
                else:
                    errors += 1
                    con.execute("INSERT INTO papers(path, folder, filename, title, year, mtime, size, status, error, "
                                "indexed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                (path, found[path], fn, title, meta.get("year") or fy, st.st_mtime, st.st_size,
                                 "error", res["error"], time.time()))
                done += 1
                if done % 25 == 0 or done == len(todo):
                    con.commit()
                    log(f"  {done}/{len(todo)}  ({time.time() - t0:.0f}s)")
        con.commit()
        con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('optimize')")
        con.commit()
    orphans = [r["path"] for r in con.execute(
        "SELECT path FROM papers WHERE dup_of IS NOT NULL AND dup_of NOT IN (SELECT id FROM papers)")]
    if orphans:
        update(workers=workers, timeout=timeout, log=log, only=orphans, embed_after=False, meta_after=False)
    if embed_after:
        embed(log=log)
    if meta_after and cfg["metadata"]["crossref"]:
        try:
            from . import meta as _meta
            _meta.update_meta(log=log)
        except Exception as e:
            log(f"metadata lookup skipped: {e}")
    return {"in_library": len(found), "indexed": done, "errors": errors, "removed": removed}


# ---------------------------------------------------------------- embeddings

_model = {}


def pick_device(device=None):
    import torch

    dev = device or config.get()["index"]["device"]
    if dev != "auto":
        return dev
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_model(device=None):
    from sentence_transformers import SentenceTransformer

    dev = pick_device(device)
    if dev not in _model:
        m = SentenceTransformer(config.get()["index"]["embed_model"], trust_remote_code=True, device=dev)
        m.max_seq_length = 1024
        if dev != "cpu":
            m.half()
        _model[dev] = m
    return _model[dev]


def embed(batch=256, log=print):
    """Embed every chunk that has no vector yet. Safe to stop and rerun."""
    import numpy as np

    con = connect()
    ids = [r[0] for r in con.execute(
        "SELECT c.id FROM chunks c LEFT JOIN vecs v ON v.chunk_id=c.id WHERE v.chunk_id IS NULL ORDER BY c.id")]
    if not ids:
        return 0
    model = get_model()
    log(f"embedding {len(ids)} chunks on {pick_device()}")
    t0 = time.time()
    for i in range(0, len(ids), batch):
        part = ids[i:i + batch]
        rows = con.execute("SELECT id, text FROM chunks WHERE id IN (%s)" % ",".join("?" * len(part)), part).fetchall()
        vecs = model.encode(["search_document: " + r["text"] for r in rows], batch_size=32,
                            normalize_embeddings=True, convert_to_numpy=True)
        vecs = np.nan_to_num(vecs).astype(np.float16)
        con.executemany("INSERT OR REPLACE INTO vecs(chunk_id, v) VALUES (?,?)",
                        [(r["id"], v.tobytes()) for r, v in zip(rows, vecs)])
        con.commit()
        n = min(i + batch, len(ids))
        el = time.time() - t0
        log(f"  {n}/{len(ids)}  ({el / 60:.1f} min, ~{el / n * (len(ids) - n) / 60:.0f} min left)")
    return len(ids)


_vec_cache = {}


def load_vectors(con):
    """All chunk vectors as one matrix, cached per process until the count changes."""
    import numpy as np

    n = con.execute("SELECT COUNT(*) FROM vecs").fetchone()[0]
    if _vec_cache.get("n") != n:
        rows = con.execute("SELECT v.chunk_id, v.v, c.is_ref, p.folder FROM vecs v JOIN chunks c ON c.id=v.chunk_id "
                           "JOIN papers p ON p.id=c.paper_id").fetchall()
        _vec_cache.update(
            n=n,
            ids=np.array([r[0] for r in rows], dtype=np.int64),
            refs=np.array([r[2] for r in rows], dtype=bool),
            folders=np.array([r[3] or "" for r in rows]),
            mat=np.vstack([np.frombuffer(r[1], dtype=np.float16) for r in rows]).astype(np.float32)
            if rows else np.zeros((0, 768), np.float32))
    return _vec_cache


# ---------------------------------------------------------------- search

STOP = set("""a an the and or of in on at to for from by with without as is are was were be been being this that
these those it its into than then there their they we our us you your he she his her which who whom whose what when where
why how not no but if so such can could may might will would should do does did done has have had also about over under
between during through via per vs versus more most less least very much many some any each other both either neither
i me my mine""".split())
TOKEN_RE = re.compile(r'"[^"]+"|[\w\-]+', re.U)


def build_match(query):
    terms = []
    for tok in TOKEN_RE.findall(query):
        if tok.startswith('"'):
            phrase = tok.strip('"').strip()
            if phrase:
                terms.append('"' + phrase.replace('"', "") + '"')
            continue
        for part in tok.split("-"):
            t = part.lower()
            if t and t not in STOP and (len(t) > 1 or t.isdigit()):
                terms.append('"' + t + '"')
    uniq = list(dict.fromkeys(terms))
    return " OR ".join(uniq), [t.strip('"') for t in uniq]


def vector_hits(con, query, k, folder=None, include_refs=False):
    import numpy as np

    vc = load_vectors(con)
    if not len(vc["ids"]):
        return []
    q = get_model("cpu").encode(["search_query: " + query], normalize_embeddings=True)[0].astype(np.float32)
    sims = vc["mat"] @ q
    mask = np.ones(len(sims), bool)
    if not include_refs:
        mask &= ~vc["refs"]
    if folder:
        mask &= np.char.startswith(vc["folders"].astype(str), folder)
    sims = np.where(mask, sims, -2)
    top = np.argsort(-sims)[:k]
    return [(int(vc["ids"][i]), float(sims[i])) for i in top if sims[i] > -2]


def keyword_hits(con, match, k, folder=None, include_refs=False):
    where, args = ["chunks_fts MATCH ?"], [match]
    if not include_refs:
        where.append("c.is_ref = 0")
    if folder:
        where.append("p.folder LIKE ?")
        args.append(f"{folder}%")
    sql = f"""SELECT c.id, -bm25(chunks_fts) AS s FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
              JOIN papers p ON p.id=c.paper_id WHERE {' AND '.join(where)} ORDER BY bm25(chunks_fts) LIMIT ?"""
    return [(r[0], r[1]) for r in con.execute(sql, args + [k])]


def highlight(text, terms):
    if not terms:
        return text
    stems = sorted({t.lower()[:max(4, len(t) - 2)] if " " not in t else t.lower() for t in terms}, key=len, reverse=True)
    pat = re.compile(r"\b(" + "|".join(re.escape(s) for s in stems) + r")[\w\-]*", re.I)
    return pat.sub(lambda m: "<<" + m.group(0) + ">>", text)


PAPER_SQL = ("SELECT c.id, c.page, c.text, p.id AS pid, p.filename, p.folder, COALESCE(m.title, p.title) AS title, "
             "COALESCE(m.year, p.year) AS year, COALESCE(m.journal, p.journal) AS journal, m.authors, m.doi, "
             "p.note, p.path FROM chunks c JOIN papers p ON p.id=c.paper_id LEFT JOIN meta m ON m.path=p.path ")


def paper_info(r, dups=None):
    info = {"id": r["pid"], "file": r["filename"], "title": r["title"], "year": r["year"], "journal": r["journal"],
            "authors": r["authors"], "doi": r["doi"], "folder": r["folder"], "pdf": r["path"], "note": r["note"]}
    if dups and r["pid"] in dups:
        info["copies"] = dups[r["pid"]]
        if not info["note"]:
            info["note"] = next((c["note"] for c in dups[r["pid"]] if c["note"]), None)
    return info


def search(query, limit=10, by_paper=False, folder=None, include_refs=False, per_paper=3, mode="hybrid"):
    """mode: hybrid (default), keyword or vector. Hybrid merges both rankings by reciprocal rank fusion."""
    con = connect()
    match, terms = build_match(query)
    if mode != "keyword" and con.execute("SELECT 1 FROM vecs LIMIT 1").fetchone() is None:
        mode = "keyword"
    pool = max(100, limit * (10 if by_paper else 3))
    kw = keyword_hits(con, match, pool, folder, include_refs) if match and mode != "vector" else []
    vec = vector_hits(con, query, pool, folder, include_refs) if mode != "keyword" else []

    fused = {}
    for src, hits in (("keyword", kw), ("vector", vec)):
        for rank, (cid, s) in enumerate(hits):
            e = fused.setdefault(cid, {"rrf": 0.0, "found_by": [], "sim": None, "bm25": None})
            e["rrf"] += 1.0 / (60 + rank + 1)
            e["found_by"].append(src)
            e["sim" if src == "vector" else "bm25"] = round(s, 3)
    order = sorted(fused.items(), key=lambda x: -x[1]["rrf"])
    if not order:
        return {"query": query, "mode": mode, "terms": terms, "results": []}

    ids = [cid for cid, _ in order]
    rows = {r["id"]: r for r in con.execute(PAPER_SQL + "WHERE c.id IN (%s)" % ",".join("?" * len(ids)), ids)}
    dups = {}
    for d in con.execute("SELECT dup_of, path, folder, note FROM papers WHERE dup_of IS NOT NULL"):
        dups.setdefault(d["dup_of"], []).append({"pdf": d["path"], "folder": d["folder"], "note": d["note"]})

    def passage(cid, e):
        r = rows[cid]
        return {"chunk_id": cid, "page": r["page"], "score": round(e["rrf"] * 1000, 2), "found_by": e["found_by"],
                "similarity": e["sim"], "bm25": e["bm25"], "passage": r["text"],
                "highlighted": highlight(r["text"], terms)}

    if not by_paper:
        return {"query": query, "mode": mode, "terms": terms, "results": [
            dict(rank=i + 1, paper=paper_info(rows[cid], dups), **passage(cid, e))
            for i, (cid, e) in enumerate(order[:limit])]}

    papers = {}
    for cid, e in order:
        r = rows[cid]
        p = papers.setdefault(r["pid"], {"info": paper_info(r, dups), "hits": []})
        if len(p["hits"]) < per_paper:
            p["hits"].append((cid, e))
    ranked = sorted(((sum([e["rrf"] for _, e in p["hits"]][:1]) + 0.5 * sum(e["rrf"] for _, e in p["hits"][1:]), p)
                     for p in papers.values()), key=lambda x: -x[0])[:limit]
    total = sum(a for a, _ in ranked) or 1
    return {"query": query, "mode": mode, "terms": terms, "results": [
        {"rank": i + 1, "score": round(a * 1000, 2), "share": round(100 * a / total, 1), "paper": p["info"],
         "passages": [passage(cid, e) for cid, e in p["hits"]]}
        for i, (a, p) in enumerate(ranked)]}


SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


def key_sentences(query, chunk_ids):
    """Score each sentence of the given chunks against the query; mark the 1-2 most relevant."""
    import numpy as np

    con = connect()
    rows = con.execute("SELECT id, text FROM chunks WHERE id IN (%s)" % ",".join("?" * len(chunk_ids)),
                       list(chunk_ids)).fetchall()
    sents = [(r["id"], s) for r in rows for s in SENT_RE.split(r["text"]) if s.strip()]
    if not sents:
        return {}
    m = get_model()
    q = m.encode(["search_query: " + query], normalize_embeddings=True)[0].astype(np.float32)
    v = m.encode(["search_document: " + s for _, s in sents], batch_size=64, normalize_embeddings=True)
    sims = np.nan_to_num(v.astype(np.float32)) @ q
    out = {}
    for (cid, s), sc in zip(sents, sims):
        out.setdefault(cid, []).append({"text": s, "score": round(float(sc), 3), "key": False})
    for lst in out.values():
        ranked = sorted(range(len(lst)), key=lambda i: -lst[i]["score"])
        best = lst[ranked[0]]["score"]
        for i in ranked[:2]:
            if lst[i]["score"] >= best - 0.04 and len(lst[i]["text"].split()) >= 5:
                lst[i]["key"] = True
        if not any(x["key"] for x in lst):
            lst[ranked[0]]["key"] = True
    return out


def stats():
    con = connect()
    q = lambda s: con.execute(s).fetchone()[0]
    return {"papers": q("SELECT COUNT(*) FROM papers"), "chunks": q("SELECT COUNT(*) FROM chunks"),
            "vectors": q("SELECT COUNT(*) FROM vecs"), "with_metadata": q("SELECT COUNT(*) FROM meta WHERE title IS NOT NULL"),
            "status": {r[0]: r[1] for r in con.execute("SELECT status, COUNT(*) FROM papers GROUP BY status")},
            "pdf_type": {r[0]: r[1] for r in con.execute("SELECT pdf_type, COUNT(*) FROM papers GROUP BY pdf_type")},
            "db_mb": round(config.get().db_path.stat().st_size / 1e6, 1) if config.get().db_path.exists() else 0}
