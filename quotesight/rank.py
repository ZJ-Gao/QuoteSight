"""Paper relevance score (0 to 10) for one search result, without Claude.

Each paper gets up to three scores, each scaled to 0..1, and the final score is their mean times 10 (score fusion):
  1. whole-paper retrieval: mean share of the paper in the hybrid ranking over the input and every query Claude ran,
     divided by the largest share in this result;
  2. Claude's judgement of the quotes it picked: mean of high 3 / medium 2 / low 1, mapped from 1..3 to 0..1, so reading
     more quotes does not inflate it;
  3. only when the user has marked papers: Rocchio relevance feedback. The query vector is moved toward the marked
     other marked papers' quotes (q' = q + 0.75 * mean of their vectors; a marked paper is scored without its own
     quotes) and each paper is scored by its best passages, min-max scaled over the papers in this result.
"""
from . import core

BETA = 0.75
W = {"high": 3, "medium": 2, "low": 1}


def _unit(values, lo=None, hi=None):
    lo = min(values.values()) if lo is None else lo
    hi = max(values.values()) if hi is None else hi
    return {k: (v - lo) / (hi - lo) if hi > lo else 1.0 for k, v in values.items()}


def _rocchio(res, by_paper, marked):
    """Leave-one-out: a marked paper is scored with feedback from the OTHER marked papers only, so marking a paper does
    not make it match its own query by construction."""
    import numpy as np
    con = core.connect()
    vc = core.load_vectors(con)
    if not len(vc["ids"]):
        return None
    pos = {int(c): i for i, c in enumerate(vc["ids"])}
    rows = {pid: [pos[f["chunk_id"]] for f in by_paper.get(pid, []) if f["chunk_id"] in pos] for pid in marked}
    if not any(rows.values()):
        return None
    qs = [res["claim"]] + [q for q in (res.get("queries") or []) if q and q != res["claim"]]
    q0 = core.get_model("cpu").encode(["search_query: " + q for q in qs], normalize_embeddings=True).astype(np.float32).mean(axis=0)
    out = {}
    for pid in by_paper:
        other = [r for m, rs in rows.items() if m != pid for r in rs]
        if not other:  # no feedback for this paper (it is the only marked one): no information, so no term
            continue
        q1 = q0 + BETA * vc["mat"][other].mean(axis=0)
        q1 /= (np.linalg.norm(q1) or 1.0)
        ids = [r[0] for r in con.execute("SELECT id FROM chunks WHERE paper_id=? AND is_ref=0", (pid,))]
        s = sorted((float(vc["mat"][pos[c]] @ q1) for c in ids if c in pos), reverse=True)[:3]
        out[pid] = sum(s) / len(s) if s else -1.0
    return out


def paper_rank(res):
    """Returns {paper_id (str): score out of 10}. Fills res['paper_scores'] when a paper is missing from it."""
    from . import llm
    by_paper = {}
    for f in res.get("findings", []):
        by_paper.setdefault(f["paper"]["id"], []).append(f)
    if not by_paper:
        return {}
    sc = res.get("paper_scores") or {}
    if any(str(p) not in sc for p in by_paper):
        llm.score_papers(res)
        sc = res.get("paper_scores") or {}
    scores = [_unit({p: sc.get(str(p), 0.0) for p in by_paper}, lo=0.0),
              _unit({p: sum(W.get(f.get("relevance"), 2) for f in fs) / len(fs) for p, fs in by_paper.items()}, lo=1.0, hi=3.0)]
    marked = set(res.get("boosted") or []) | {p for p, fs in by_paper.items() if any(f.get("added") for f in fs)}
    marked &= set(by_paper)
    if marked:
        r3 = _rocchio(res, by_paper, marked)
        if r3:
            scores.append(_unit(r3))
    # a paper with no score from some term (no feedback available for it) is averaged over the terms it has
    return {str(p): round(10 * sum(s[p] for s in scores if p in s) / sum(1 for s in scores if p in s), 1) for p in by_paper}
