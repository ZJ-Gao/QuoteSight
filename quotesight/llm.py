"""Evidence search with an LLM, through a local command-line agent (Claude Code or Codex CLI).

Pipeline (no tool permissions are given to the model):
1. plan    the model turns the user's input into 2-4 search queries
2. search  QuoteSight runs them (hybrid search) and collects the best passages
3. select  the model picks verbatim quotes, a stance and a short note for each
4. verify  every quote is checked against the stored passage text

Both CLIs run on the user's own subscription or login; no API key is needed. Token usage and, for
Claude, the account's rate-limit windows are read from the CLI's JSON stream.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, core

PROMPTS = Path(__file__).parent / "prompts"

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"kind": {"type": "string", "enum": ["claim", "topic"]},
                   "queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["kind", "queries"],
}
SELECT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"chunk_id": {"type": "integer"}, "quote": {"type": "string"},
                           "stance": {"type": "string", "enum": ["support", "refute", "context"]},
                           "note": {"type": "string"},
                           "relevance": {"type": "string", "enum": ["high", "medium", "low"]}},
            "required": ["chunk_id", "quote", "stance", "note", "relevance"]}},
    },
    "required": ["summary", "findings"],
}


def history_dir():
    d = config.get().data_dir / "history"
    d.mkdir(exist_ok=True)
    return d


def prompt(name, **kw):
    cfg = config.get()
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    kw.setdefault("description", cfg["library"]["description"])
    kw.setdefault("language", cfg["llm"]["language"])
    return text.format(**kw)


def _json_from_text(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else None


def _exe(name):
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"`{name}` was not found on PATH. Install it and log in first.")
    return path


def _windows_script(path):
    return sys.platform.startswith("win") and path.lower().endswith((".cmd", ".bat"))


class Usage:
    def __init__(self):
        self.tokens = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
        self.cost = 0.0
        self.limits = None
        self.model = None

    def add(self, d):
        for k in self.tokens:
            self.tokens[k] += d.get(k, 0) or 0

    def total(self):
        return sum(self.tokens.values())


def call_claude(system, user, schema, usage, emit, model=None):
    cfg = config.get()["llm"]
    exe = _exe("claude")
    cmd = [exe, "-p", "--model", model or cfg["claude_model"], "--effort", cfg["claude_effort"],
           "--output-format", "stream-json", "--verbose", "--system-prompt", system, "--tools", "",
           "--strict-mcp-config", "--disable-slash-commands", "--setting-sources", "", "--no-session-persistence"]
    if not _windows_script(exe):
        cmd += ["--json-schema", json.dumps(schema)]
    else:
        user += "\n\nReturn JSON matching this schema:\n" + json.dumps(schema)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", cwd=tempfile.gettempdir())
    proc.stdin.write(user)
    proc.stdin.close()
    result = None
    for line in proc.stdout:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t = d.get("type")
        if t == "rate_limit_event":
            win = (d.get("rate_limit_info") or {}).get("unifiedWindows") or {}
            usage.limits = {k: {"used": v.get("utilization"), "resets_at": v.get("resetsAt")} for k, v in win.items()}
            emit({"kind": "limits", "limits": usage.limits})
        elif t == "result":
            result = d
    proc.wait()
    if not result or result.get("is_error"):
        raise RuntimeError((result or {}).get("result") or proc.stderr.read()[-800:] or "Claude returned nothing")
    u = result.get("usage") or {}
    usage.add({"input": u.get("input_tokens"), "cache_write": u.get("cache_creation_input_tokens"),
               "cache_read": u.get("cache_read_input_tokens"), "output": u.get("output_tokens")})
    usage.cost += result.get("total_cost_usd") or 0
    mids = list((result.get("modelUsage") or {}).keys())
    if mids:
        m = re.match(r"claude-([a-z]+)-(\d+)-(\d+)", mids[0])
        usage.model = f"{m.group(1).title()} {m.group(2)}.{m.group(3)}" if m else mids[0]
    emit({"kind": "usage", "tokens": dict(usage.tokens)})
    return result.get("structured_output") or _json_from_text(result.get("result"))


def call_codex(system, user, schema, usage, emit, model=None):
    cfg = config.get()["llm"]
    exe = _exe("codex")
    with tempfile.TemporaryDirectory() as tmp:
        sp = Path(tmp) / "schema.json"
        sp.write_text(json.dumps(schema), encoding="utf-8")
        cmd = [exe, "exec", "--json", "--output-schema", str(sp), "--sandbox", "read-only", "--skip-git-repo-check",
               "-c", f'model_reasoning_effort="{cfg["codex_effort"]}"']
        if model or cfg["codex_model"]:
            cmd += ["--model", model or cfg["codex_model"]]
        cmd.append("-")
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace", cwd=tmp)
        proc.stdin.write(system + "\n\n---\n\n" + user)
        proc.stdin.close()
        text = None
        for line in proc.stdout:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "item.completed" and (d.get("item") or {}).get("type") == "agent_message":
                text = d["item"].get("text")
            elif d.get("type") == "turn.completed":
                u = d.get("usage") or {}
                usage.add({"input": (u.get("input_tokens") or 0) - (u.get("cached_input_tokens") or 0),
                           "cache_read": u.get("cached_input_tokens"), "output": u.get("output_tokens")})
                emit({"kind": "usage", "tokens": dict(usage.tokens)})
            elif d.get("type") in ("error", "turn.failed"):
                raise RuntimeError(json.dumps(d)[:800])
        proc.wait()
        usage.model = cfg["codex_model"] or "Codex"
    if text is None:
        raise RuntimeError(proc.stderr.read()[-800:] or "Codex returned nothing")
    return _json_from_text(text)


# To add a model or provider: write call_<name>(system, user, schema, usage, emit) like the two above,
# register it here, and add <name>_model / <name>_effort to [llm] in the config. See prompts/add_model.md.
BACKENDS = {"claude": call_claude, "codex": call_codex}
LABELS = {"claude": "Claude", "codex": "Codex"}


_CITE = re.compile(r"^\d{1,3}(?:\s*[,–-]\s*\d{1,3})*$")
_UNIT = re.compile(r"(?:^|[^A-Za-z])(?:k?m|cm|mm|s|yr|ka|Ma|g|kg|L|ha)\s?$")


def strip_cites(s):
    """Drop superscript citation numbers (landslides<sup>3,55–57</sup>) but keep isotopes
    (<sup>10</sup>Be), exponents (s<sup>–1</sup>) and units (km<sup>2</sup>)."""
    s = s or ""

    def sup(m):
        x, before = m.group(1).strip(), s[max(0, m.start() - 4):m.start()]
        if not _CITE.match(x) or _UNIT.search(before) or not re.search(r"[A-Za-z.,;:)\]]$", before):
            return m.group(0)
        return ""
    s = re.sub(r"<sup>([^<]*)</sup>(?![A-Za-z])", sup, s)
    return re.sub(r"([a-z)])(\d{1,3}(?:[,–]\d{1,3})+)(?=[\s.,;:)]|$)", r"\1", s)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"</?su[pb]>", "", s.lower()))


def verify(quote, text):
    """True if the quote appears in the passage, ignoring spacing, punctuation and citation numbers."""
    return _match(quote, text) or _match(strip_cites(quote), strip_cites(text))


def _match(quote, text):
    q, t = _norm(quote), _norm(text)
    if not q:
        return False
    if q in t:
        return True
    pieces = [q[i:i + 40] for i in range(0, max(1, len(q) - 39), 20)]
    return sum(p in t for p in pieces) >= 0.8 * len(pieces)


# Two depths: "standard" (~30 s) and "broad" (~60 s: more queries for a topic, more passages, and sentences from
# papers that only mention the topic in passing are kept as "low" relevance instead of dropped).
DEPTH = {
    "standard": {"n_queries": "2 to 4", "max_queries": 4, "passages_key": "max_passages",
                 "keep_rule": "Drop passages that only share the topic or the words."},
    "broad": {"n_queries": "3 or 4 for a claim, 5 or 6 for a topic", "max_queries": 6, "passages_key": "max_passages_broad",
              "keep_rule": "Also keep sentences from papers whose main subject is something else but that say something specific about the input (a value, a case, a comparison, a stated mechanism); mark these \"low\" rather than dropping them. Drop passages that only share the words."},
}


def run(text, backend=None, on_event=None, language=None, max_findings=20, depth="standard"):
    cfg = config.get()
    language = language or cfg["llm"]["language"]
    backend = backend or cfg["llm"]["backend"]
    call = BACKENDS.get(backend)
    if not call:
        return {"ok": False, "error": f"unknown LLM backend: {backend}"}
    emit = on_event or (lambda e: None)
    usage = Usage()
    t0 = time.time()
    try:
        emit({"kind": "status", "text": "planning queries"})
        D = DEPTH.get(depth, DEPTH["standard"])
        plan = call(prompt("plan", language=language, n_queries=D["n_queries"]), "Input: " + text, PLAN_SCHEMA, usage, emit) or {}
        queries = [q for q in plan.get("queries", []) if q.strip()][:D["max_queries"]] or [text]
        kind = plan.get("kind", "claim")
        for q in queries:
            emit({"kind": "query", "text": q})

        emit({"kind": "status", "text": f"searching ({len(queries)} queries)"})
        seen, passages = set(), []
        budget = cfg["llm"].get(D["passages_key"]) or cfg["llm"]["max_passages"]
        per = max(6, budget // len(queries))
        for q in queries + [text]:
            for r in core.search(q, limit=per, max_per_paper=2)["results"]:
                if r["chunk_id"] not in seen:
                    seen.add(r["chunk_id"])
                    passages.append(r)
        passages = passages[:budget]
        block = "\n\n".join(f"[#{r['chunk_id']}] {r['paper']['file']} | {r['paper']['folder']} | p.{r['page']}\n"
                            f"{r['passage']}" for r in passages)

        emit({"kind": "status", "text": f"reading {len(passages)} passages"})
        max_findings = max(1, min(int(max_findings or 20), 20))
        out = call(prompt("select", kind=kind, language=language, max_findings=max_findings, keep_rule=D["keep_rule"]), f"Input: {text}\n\nPassages:\n\n{block}", SELECT_SCHEMA, usage, emit)
        if not out:
            raise RuntimeError("could not parse the model's answer")
    except Exception as e:
        return {"ok": False, "error": str(e), "tokens": dict(usage.tokens, total=usage.total()),
                "limits": usage.limits, "seconds": round(time.time() - t0, 1)}

    con = core.connect()
    findings = []
    for f in out.get("findings", []):
        row = con.execute(core.PAPER_SQL + "WHERE c.id=?", (f.get("chunk_id"),)).fetchone()
        if row:
            findings.append({"chunk_id": row["id"], "page": row["page"], "quote": f["quote"], "stance": f["stance"],
                             "note": f.get("note", ""), "relevance": f.get("relevance", "medium"),
                             "verified": verify(f["quote"], row["text"]),
                             "passage": row["text"], "paper": core.paper_info(row)})
    res = {"ok": True, "claim": text, "kind": kind, "backend": backend, "model_name": usage.model,
           "effort": cfg["llm"].get(f"{backend}_effort"), "depth": depth, "summary": out.get("summary", ""), "queries": queries,
           "findings": findings, "n_passages": len(passages), "tokens": dict(usage.tokens, total=usage.total()),
           "cost_usd_list_price": round(usage.cost, 4), "limits": usage.limits,
           "seconds": round(time.time() - t0, 1), "time": time.time()}
    hid = time.strftime("%Y%m%d-%H%M%S")
    res["history_id"] = hid
    (history_dir() / f"{hid}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _hist_sub(name):
    d = history_dir() / name  # "archive": topics not active now; "trash": deleted searches, recoverable by hand
    d.mkdir(exist_ok=True)
    return d


def list_history(archived=False):
    out = []
    for p in sorted((_hist_sub("archive") if archived else history_dir()).glob("*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": p.stem, "claim": d.get("claim"), "model": d.get("model_name") or d.get("backend"),
                    "n": len(d.get("findings", [])), "tokens": (d.get("tokens") or {}).get("total"), "time": d.get("time"),
                    "archived": archived,
                    "text": " ".join([d.get("summary", "")] + [f.get("quote", "") + " " + f["paper"].get("file", "")
                                                              for f in d.get("findings", [])])})
    return out


def _hist_path(hid):
    if not re.fullmatch(r"[0-9-]+", hid):
        return None
    for d in (history_dir(), _hist_sub("archive")):
        if (d / f"{hid}.json").is_file():
            return d / f"{hid}.json"
    return None


def move_history(hid, action):
    """action: 'archive', 'unarchive' or 'delete' (moved to history/trash, recoverable by hand)."""
    p = _hist_path(hid)
    dest = {"archive": _hist_sub("archive"), "unarchive": history_dir(), "delete": _hist_sub("trash")}.get(action)
    if not p or dest is None:
        return False
    p.replace(dest / p.name)
    return True


def load_history(hid):
    p = _hist_path(hid)
    if not p:
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    con = core.connect()
    for f in d.get("findings", []):
        row = con.execute(core.PAPER_SQL + "WHERE c.id=?", (f.get("chunk_id"),)).fetchone()
        if row:
            f["paper"] = core.paper_info(row)
    return d
