"""Local web board: http://127.0.0.1:8765 by default. Listens on localhost only."""
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from . import config, core, llm, rank

HERE = Path(__file__).parent
app = FastAPI()
lock = threading.Lock()
llm_lock = threading.Lock()
job = {"running": False, "log": [], "result": None}
asks = {}


def _last_limits():
    for h in llm.list_history()[:20]:
        d = llm.load_history(h["id"]) or {}
        if d.get("limits"):
            return d["limits"]
    return None


hud = {"limits": None, "app_tokens": 0, "app_searches": 0, "model_name": None, "effort": None, "backend": None}


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/{name}", include_in_schema=False)
def icon(name: str):
    files = {"favicon.ico": "favicon.png", "favicon.png": "favicon.png", "favicon.svg": "favicon.svg",
             "apple-touch-icon.png": "apple-touch-icon.png"}
    if name not in files:
        raise HTTPException(404)
    return FileResponse(HERE / "static" / files[name])


@app.get("/api/config")
def api_config():
    cfg = config.get()
    return {"backend": cfg["llm"]["backend"],
            "backends": [{"name": n, "label": llm.LABELS.get(n, n.title())} for n in llm.BACKENDS],
            "models": {n: cfg["llm"].get(f"{n}_model") or "default" for n in llm.BACKENDS},
            "ui_language": cfg["app"].get("ui_language", "en"),
            "effort": cfg["llm"].get(f"{cfg['llm']['backend']}_effort")}


@app.post("/api/ask")
def api_ask(body: dict):
    q = (body.get("q") or "").strip()
    backend = body.get("backend") or config.get()["llm"]["backend"]
    depth = "broad" if body.get("depth") == "broad" else "standard"
    language = {"zh": "Chinese", "en": "English"}.get(body.get("lang"))
    try:
        max_findings = max(1, min(int(body.get("max") or 20), 20))
    except (TypeError, ValueError):
        max_findings = 20
    try:
        per_paper = max(1, min(int(body.get("per") or 5), 10))
    except (TypeError, ValueError):
        per_paper = 5
    if not q:
        raise HTTPException(400)
    jid = str(len(asks) + 1)
    j = {"id": jid, "running": True, "status": "queued", "queries": [], "tokens": None, "result": None,
         "started": time.time()}
    asks[jid] = j

    def on_event(e):
        if e["kind"] == "status":
            j["status"] = e["text"]
        elif e["kind"] == "query":
            j["queries"].append(e["text"])
        elif e["kind"] == "usage":
            j["tokens"] = e["tokens"]
        elif e["kind"] == "limits":
            hud["limits"] = e["limits"]

    def go():
        with llm_lock:
            try:
                res = llm.run(q, backend=backend, on_event=on_event, language=language, max_findings=max_findings, depth=depth, per_paper=per_paper)
            except Exception as ex:
                res = {"ok": False, "error": str(ex)}
            if res.get("ok"):
                try:
                    with lock:
                        llm.repair_findings(res)
                        llm.score_papers(res)
                        res["rank"] = rank.paper_rank(res)
                    llm.rewrite_history(res)
                except Exception:
                    pass
            j["result"] = res
            if res.get("tokens"):
                hud["app_tokens"] += res["tokens"].get("total", 0)
                hud["app_searches"] += 1
            for k in ("limits", "model_name", "effort", "backend"):
                if res.get(k):
                    hud[k] = res[k]
            j["running"] = False

    threading.Thread(target=go, daemon=True).start()
    return {"id": jid}


@app.get("/api/ask/{jid}")
def api_ask_status(jid: str):
    j = asks.get(jid)
    if not j:
        raise HTTPException(404)
    return dict(j, elapsed=round(time.time() - j["started"], 1), hud=hud)


@app.get("/api/fast")
def api_fast(q: str, folder: str = ""):
    """Quick mode without an LLM: hybrid search, key sentences picked by the embedding model."""
    t0 = time.time()
    with lock:
        res = core.search(q, limit=12, by_paper=True, folder=folder or None, per_paper=2)
        ids = [h["chunk_id"] for r in res["results"] for h in r["passages"]]
        keys = core.key_sentences(q, ids) if ids else {}
    findings = []
    for r in res["results"]:
        for h in r["passages"]:
            ks = [s["text"] for s in keys.get(h["chunk_id"], []) if s["key"]]
            findings.append({"chunk_id": h["chunk_id"], "page": h["page"], "quote": " ".join(ks) or h["passage"][:400],
                             "stance": "match", "note": "", "verified": True, "paper": r["paper"]})
    return {"ok": True, "claim": q, "summary": "", "queries": [q], "findings": findings,
            "seconds": round(time.time() - t0, 1)}


@app.get("/api/history")
def api_history(archived: bool = False):
    return llm.list_history(archived)


@app.post("/api/history/{hid}/boost")
def api_history_boost(hid: str, body: dict):
    d = llm.load_history(hid)
    if not d:
        raise HTTPException(404)
    ids = [x for x in d.get("boosted", []) if x != body.get("paper_id")]
    if body.get("on"):
        ids.append(body.get("paper_id"))
    d["boosted"] = ids
    llm.rewrite_history(dict(d, history_id=hid))
    return {"ok": True}


@app.post("/api/history/{hid}/extend")
def api_history_extend(hid: str, body: dict):
    """Save quotes the user added from the extra papers into that search's history file."""
    d = llm.load_history(hid)
    if not d:
        raise HTTPException(404)
    have = {f["chunk_id"] for f in d.get("findings", [])}
    for f in body.get("findings") or []:
        if f.get("chunk_id") not in have:
            f = dict(f, added=True)
            f.pop("extra", None)
            d["findings"].append(f)
    llm.rewrite_history(dict(d, history_id=hid))
    return {"ok": True}


@app.post("/api/history/{hid}/{action}")
def api_history_move(hid: str, action: str):
    if action not in ("archive", "unarchive", "delete") or not llm.move_history(hid, action):
        raise HTTPException(404)
    return {"ok": True}


@app.post("/api/vocab")
def api_vocab_add(body: dict):
    from . import vocab
    language = {"zh": "Chinese", "en": "English"}.get(body.get("lang"))
    try:
        with llm_lock:
            e = vocab.add(body.get("word"), body.get("context"), body.get("paper_id"), body.get("page"), language=language)
    except Exception as ex:
        return {"ok": False, "error": str(ex)}
    if not e.get("duplicate"):
        hud["app_tokens"] += e.get("tokens", 0)
    return {"ok": True, "entry": e}


@app.get("/api/vocab")
def api_vocab_list():
    from . import vocab
    return list(reversed(vocab.load()))


@app.get("/api/marks")
def api_marks():
    from . import marks
    return marks.list_marks()


@app.post("/api/marks")
def api_marks_add(body: dict):
    from . import marks
    try:
        return {"ok": True, "mark": marks.add(body.get("paper_id"), body.get("page"), body.get("text"), body.get("stance"))}
    except (ValueError, TypeError) as ex:
        return {"ok": False, "error": str(ex)}


@app.post("/api/marks/{mid}/{action}")
def api_marks_change(mid: str, action: str, stance: str = ""):
    from . import marks
    ok = marks.delete(mid) if action == "delete" else marks.update(mid, stance) if action == "stance" else False
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@app.get("/api/history/{hid}")
def api_history_get(hid: str):
    d = llm.load_history(hid)
    if not d:
        raise HTTPException(404)
    if any(f.get("passage") and not llm.verify(f["quote"], f["passage"]) for f in d.get("findings", [])):
        with lock:
            llm.repair_findings(d)
        llm.rewrite_history(dict(d, history_id=hid))
    if llm.clean_findings(d.get("findings", [])):
        llm.rewrite_history(dict(d, history_id=hid))
    for f in d.get("findings", []):
        if f.get("passage"):
            f["verified"] = llm.verify(f["quote"], f["passage"])
    if d.get("findings") and d.get("claim"):
        with lock:
            n0 = len(d.get("paper_scores") or {})
            d["rank"] = rank.paper_rank(d)
        if len(d.get("paper_scores") or {}) != n0:
            llm.rewrite_history(dict(d, history_id=hid))
    return d


@app.get("/api/rank/{hid}")
def api_rank(hid: str):
    d = llm.load_history(hid)
    if not d:
        raise HTTPException(404)
    with lock:
        n0 = len(d.get("paper_scores") or {})
        rk = rank.paper_rank(d)
    if len(d.get("paper_scores") or {}) != n0:
        llm.rewrite_history(dict(d, history_id=hid))
    return {"rank": rk, "paper_scores": d.get("paper_scores")}


@app.get("/api/more")
def api_more(q: str, exclude: str = "", n: int = 15):
    """Papers ranked below the ones the model read: key sentences by the embedding model, no tokens."""
    skip = {int(x) for x in exclude.split(",") if x.strip().isdigit()}
    with lock:
        res = core.search(q, limit=80, by_paper=True, per_paper=2)
        rows = [r for r in res["results"] if r["paper"]["id"] not in skip][:max(1, min(n, 30))]
        ids = [h["chunk_id"] for r in rows for h in r["passages"]]
        keys = core.key_sentences(q, ids) if ids else {}
    findings = []
    for r in rows:
        for h in r["passages"]:
            ks = [s["text"] for s in keys.get(h["chunk_id"], []) if s["key"]]
            findings.append({"chunk_id": h["chunk_id"], "page": h["page"], "quote": " ".join(ks) or h["passage"][:400],
                             "stance": "match", "note": "", "verified": True, "passage": h["passage"],
                             "paper": r["paper"], "extra": True})
    return {"ok": True, "findings": findings}


@app.post("/api/addpaper")
def api_addpaper(body: dict):
    """The model reads one whole paper against the claim; the result is saved into that search's history."""
    claim = (body.get("claim") or "").strip()
    language = {"zh": "Chinese", "en": "English"}.get(body.get("lang"))
    try:
        pid = int(body.get("paper_id"))
        per = max(0, min(int(body.get("per", 5)), 20))  # 0 = the model decides
    except (TypeError, ValueError):
        raise HTTPException(400)
    if not claim:
        raise HTTPException(400)
    have = [str(q) for q in (body.get("have") or [])][:30]
    with llm_lock:
        r = llm.read_paper(claim, pid, backend=body.get("backend") or None, language=language, per_paper=per, have=have)
    if r.get("ok") and body.get("hid"):
        api_history_extend(body["hid"], {"findings": r["findings"]})
    return r


@app.get("/api/hud")
def api_hud():
    return hud


@app.get("/api/stats")
def api_stats():
    return core.stats()


def _pdf_path(pid):
    row = core.connect().execute("SELECT path FROM papers WHERE id=?", (pid,)).fetchone()
    if not row or not os.path.isfile(row[0]):
        raise HTTPException(404)
    return row[0]


@app.get("/pdf/{pid}")
def pdf(pid: int):
    return FileResponse(_pdf_path(pid), media_type="application/pdf")


@app.post("/api/open/{pid}")
def open_pdf(pid: int):
    """Open the PDF in the system's default viewer."""
    path = _pdf_path(pid)
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return {"ok": True}


@app.post("/api/update")
def api_update():
    if job["running"]:
        return {"running": True}

    def run():
        job.update(running=True, log=[], result=None)
        try:
            job["result"] = core.update(log=lambda m: job["log"].append(m))
        except Exception as e:
            job["result"] = {"error": str(e)}
        finally:
            job["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return {"running": True}


@app.get("/api/update")
def api_update_status():
    return {"running": job["running"], "log": job["log"][-3:], "result": job["result"]}


def main(open_browser=True, port=None):
    import uvicorn

    cfg = config.get()
    hud["limits"] = _last_limits()
    port = port or cfg["app"]["port"]
    print("loading the embedding model ...", file=sys.stderr, flush=True)
    core.get_model("cpu").encode(["search_query: warm up"])
    core.get_model().encode(["search_document: warm up"])
    core.load_vectors(core.connect())
    url = f"http://{cfg['app']['host']}:{port}"
    print(f"quotesight-app ready: {url}", file=sys.stderr, flush=True)
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=cfg["app"]["host"], port=port, log_level="warning")
