"""Bibliographic metadata (title, authors, journal, year, DOI) from Crossref.

A DOI is taken from the first two pages; otherwise Crossref is searched with the file name's author and
year plus the opening text. A Crossref record is accepted only if its title appears in the first pages.
Stored in the `meta` table keyed by PDF path, so re-indexing text does not lose it.
"""
import html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import config, core


def _ua():
    mailto = config.get()["metadata"].get("mailto")
    return "QuoteSight/0.1" + (f" (mailto:{mailto})" if mailto else "")


try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>()\[\],;]+", re.I)



def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": _ua()})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


_SUP = str.maketrans("0123456789+-‐−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻")
_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def clean_title(t):
    """Crossref titles carry JATS markup and HTML entities: '&gt;', '<scp>CT</scp>', 'δ <sup>18</sup> O'."""
    t = html.unescape(t or "")

    def script(m):
        prev, tag, body = m.group(1), m.group(2), m.group(3).strip()
        mapped = body.translate(_SUP if tag == "sup" else _SUB)
        if any(c in "0123456789+-‐−" for c in mapped):  # not fully mappable: keep plain text
            mapped = body
        join = len(re.sub(r"\W", "", prev)) <= 2  # 'δ¹⁸O', 'km³', '¹⁰Be'; but 'from ¹⁰Be'
        return prev + ("" if join else " ") + mapped
    t = re.sub(r"(\S*)\s*<(sup|sub)>(.*?)</\2>\s*", script, t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\(\s+", "(", re.sub(r"\s+([),.:;])", r"\1", t))
    return t.strip()


def _record(msg):
    if not msg:
        return None
    title = clean_title(" ".join(msg.get("title") or []))
    authors = []
    for a in msg.get("author") or []:
        fam = a.get("family") or a.get("name") or ""
        giv = a.get("given") or ""
        if fam:
            authors.append((fam + (", " + giv if giv else "")).strip())
    journal = (msg.get("container-title") or [""])[0]
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(k) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    return {"doi": msg.get("DOI"), "title": title, "authors": "; ".join(authors), "journal": journal, "year": year}


def _title_in(title, text):
    t, x = _norm(title), _norm(text)
    if len(t) < 12:
        return False
    if t[:60] in x:
        return True
    words = [w for w in re.findall(r"[a-z]{4,}", title.lower())]
    return bool(words) and sum(_norm(w) in x for w in words) >= 0.85 * len(words)


def _clean_doi(d):
    d = d.rstrip(".")
    for suf in ("/abstract", "/full", "/pdf", ".pdf"):
        if d.lower().endswith(suf):
            d = d[: -len(suf)]
    return d


def lookup(fn, text):
    """Return (record, source) or (None, reason)."""
    dois = []
    for m in DOI_RE.finditer(text):
        d = _clean_doi(m.group(0))
        if d.lower() not in [x.lower() for x in dois]:
            dois.append(d)
    for d in dois[:4]:
        res = _get("https://api.crossref.org/works/" + urllib.parse.quote(d, safe="/"))
        rec = _record((res or {}).get("message"))
        if rec and _title_in(rec["title"], text):
            return rec, "crossref-doi"
    stem = re.sub(r"\.pdf$", "", fn, flags=re.I)
    author = re.split(r"[ ,_]", stem)[0]
    year = re.search(r"(19|20)\d{2}", stem)
    q = " ".join([author, year.group(0) if year else "", re.sub(r"\s+", " ", text[:400])])
    params = {"query.bibliographic": q[:500], "rows": "5"}
    if author and len(author) > 2:
        params["query.author"] = author
    res = _get("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
    for item in ((res or {}).get("message") or {}).get("items") or []:
        rec = _record(item)
        if rec and _title_in(rec["title"], text):
            return rec, "crossref-search"
    return None, "not found"


def first_text(con, pid):
    return " ".join(r[0] for r in con.execute(
        "SELECT text FROM chunks WHERE paper_id=? AND page<=2 ORDER BY page, ord", (pid,)))


def update_meta(force=False, log=print, workers=4):
    con = core.connect()
    for path, title in con.execute("SELECT path, title FROM meta WHERE title LIKE '%<%' OR title LIKE '%&%;%'").fetchall():
        con.execute("UPDATE meta SET title=? WHERE path=?", (clean_title(title), path))  # titles stored before cleaning
    con.commit()
    done = {r[0] for r in con.execute("SELECT path FROM meta")}
    rows = con.execute("SELECT id, path, filename FROM papers WHERE status='ok'").fetchall()
    todo = [r for r in rows if force or r["path"] not in done]
    if not todo:
        return {"checked": 0}
    log(f"looking up metadata for {len(todo)} papers")
    texts = {r["id"]: first_text(con, r["id"]) for r in todo}

    def work(r):
        rec, src = lookup(r["filename"], texts[r["id"]])
        return r, rec, src

    found = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (r, rec, src) in enumerate(ex.map(work, todo), 1):
            rec = rec or {}
            found += bool(rec)
            con.execute("INSERT OR REPLACE INTO meta(path, doi, title, authors, journal, year, source, checked_at) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (r["path"], rec.get("doi"), rec.get("title"), rec.get("authors"), rec.get("journal"),
                         rec.get("year"), src, time.time()))
            if i % 25 == 0 or i == len(todo):
                con.commit()
                log(f"  {i}/{len(todo)}  found {found}")
    con.commit()
    return {"checked": len(todo), "found": found}
