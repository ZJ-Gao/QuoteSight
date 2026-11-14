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

from . import config, core, llm

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


@app.get("/api/config")
def api_config():
    cfg = config.get()
    return {"obsidian": cfg.obsidian_enabled, "backend": cfg["llm"]["backend"],
            "models": {"claude": cfg["llm"]["claude_model"], "codex": cfg["llm"]["codex_model"] or "default"},
            "ui_language": cfg["app"].get("ui_language", "en"),
            "effort": cfg["llm"][f"{cfg['llm']['backend']}_effort"] if cfg["llm"]["backend"] in llm.BACKENDS else None}


@app.post("/api/ask")
def api_ask(body: dict):
    q = (body.get("q") or "").strip()
    backend = body.get("backend") or config.get()["llm"]["backend"]
    language = {"zh": "Chinese", "en": "English"}.get(body.get("lang"))
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
                res = llm.run(q, backend=backend, on_event=on_event, language=language)
            except Exception as ex:
                res = {"ok": False, "error": str(ex)}
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
def api_history():
    return llm.list_history()


@app.get("/api/history/{hid}")
def api_history_get(hid: str):
    d = llm.load_history(hid)
    if not d:
        raise HTTPException(404)
    return d


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
    """Open the PDF in the system's default viewer (used when Obsidian is off)."""
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
