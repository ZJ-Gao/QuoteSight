"""Command-line entry points: quotesight, quotesight-search, quotesight-app."""
import argparse
import json
import shutil
import sys
from pathlib import Path

from . import config


def _common(ap):
    ap.add_argument("--config", help="path to config.toml (default: ./config.toml or the user config folder)")


def _out(s):
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    print(s)


def main_search(argv=None):
    ap = argparse.ArgumentParser(
        prog="quotesight-search", description="Search the full text of every PDF in the library. Prints JSON by default.")
    ap.add_argument("query", nargs="+", help='keywords or a claim; put exact phrases in "double quotes"')
    ap.add_argument("-n", "--limit", type=int, default=10, help="number of results (default 10)")
    ap.add_argument("-p", "--by-paper", action="store_true", help="group by paper with a relevance share (%%)")
    ap.add_argument("-f", "--folder", help="restrict to a topic folder (prefix of its name)")
    ap.add_argument("-m", "--mode", choices=["hybrid", "keyword", "vector"], default="hybrid")
    ap.add_argument("--refs", action="store_true", help="also search reference lists (off by default)")
    ap.add_argument("-c", "--compact", action="store_true",
                    help="compact text for agents: [#chunk_id] file | topic | p.N, then the passage")
    ap.add_argument("-t", "--text", action="store_true", help="human-readable output")
    ap.add_argument("--per-paper", type=int, default=None, metavar="N",
                    help="passage mode: at most N passages from one paper (spreads results over more papers)")
    ap.add_argument("--ask", action="store_true", help="use the configured LLM to pick verbatim evidence")
    ap.add_argument("--broad", action="store_true",
                    help="with --ask: broad search (more queries and passages, about twice the time and tokens)")
    _common(ap)
    a = ap.parse_args(argv)
    config.get(a.config)
    from . import core

    q = " ".join(a.query)
    if a.ask:
        from . import llm
        res = llm.run(q, on_event=lambda e: print(f"[{e['kind']}] {e.get('text', '')}", file=sys.stderr)
                      if e["kind"] in ("status", "query") else None, depth="broad" if a.broad else "standard")
        if a.text and res.get("ok"):
            _out(res["summary"] + "\n")
            for f in res["findings"]:
                _out(f"[{f['stance']}, {f.get('relevance', '')}] {f['paper']['file']} p.{f['page']}{'' if f['verified'] else ' (unverified)'}\n"
                     f"  \"{f['quote']}\"\n  {f['note']}\n")
            _out(f"tokens: {res['tokens']['total']}  time: {res['seconds']} s")
        else:
            _out(json.dumps(res, ensure_ascii=False, indent=1))
        return
    res = core.search(q, limit=a.limit, by_paper=a.by_paper, folder=a.folder, include_refs=a.refs, mode=a.mode,
                      max_per_paper=a.per_paper)
    if a.compact:
        for r in res["results"]:
            p = r["paper"]
            for h in r.get("passages", [r]):
                _out(f"[#{h['chunk_id']}] {p['file']} | {p['folder']} | p.{h['page']}\n{h['passage']}\n")
        return
    if not a.text:
        _out(json.dumps(res, ensure_ascii=False, indent=1))
        return
    _out(f"mode: {res['mode']}   terms: {', '.join(res['terms'])}\n")
    for r in res["results"]:
        p = r["paper"]
        head = f"{r['rank']}. {p['file']}  [{p['folder']}]"
        if "share" in r:
            _out(f"{head}  {r['share']}%")
            for h in r["passages"]:
                _out(f"   p.{h['page']} [{'+'.join(h['found_by'])}]: {h['highlighted'][:400]}\n")
        else:
            _out(f"{head}  p.{r['page']}  [{'+'.join(r['found_by'])}]\n   {r['highlighted'][:500]}\n")


def doctor():
    cfg = config.get()
    ok = lambda b: "ok  " if b else "MISSING"
    print(f"config file      : {cfg.path or 'none found (using defaults)'}")
    print(f"python           : {sys.version.split()[0]}")
    for r in cfg.roots or []:
        print(f"library root     : {ok(r.is_dir())} {r}")
    if not cfg.roots:
        print("library root     : MISSING  set [library] roots in the config file")
    print(f"data folder      : {cfg.data_dir}")
    for mod in ("pdf_inspector", "sentence_transformers", "fastapi", "numpy"):
        try:
            __import__(mod)
            print(f"python package   : ok   {mod}")
        except ImportError:
            print(f"python package   : MISSING {mod}")
    try:
        from . import core
        print(f"compute device   : {core.pick_device()}")
    except Exception as e:
        print(f"compute device   : ? ({e})")
    for exe in ("claude", "codex"):
        print(f"LLM command      : {ok(shutil.which(exe))} {exe}{'  <- selected' if cfg['llm']['backend'] == exe else ''}")


def init_config(target):
    example = Path(__file__).resolve().parent.parent / "config.example.toml"
    target = Path(target).expanduser()
    if target.exists():
        print(f"{target} already exists; not overwritten.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if example.is_file():
        target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target.write_text("[library]\nroots = []\n", encoding="utf-8")
    print(f"wrote {target}; edit it, then run: quotesight doctor")


def _ask(question, default=""):
    tip = f" [{default}]" if default else ""
    ans = input(f"{question}{tip}: ").strip()
    return ans or default


def _toml_path(p):
    return "'" + str(p).replace("'", "") + "'"


def setup(target="config.toml"):
    """Four questions, then write config.toml. Run by the installers."""
    import platform

    repo = Path(__file__).resolve().parent.parent
    target = Path(target) if Path(target).is_absolute() else repo / target
    system = {"Darwin": "macOS", "Windows": "Windows"}.get(platform.system(), platform.system())
    print(f"\n1. System: {system} (detected)")

    from . import llm
    names = list(llm.BACKENDS)
    found = [x for x in names if shutil.which(x)]
    print(f"\n2. Coding agent for the precise search. Found on this computer: {', '.join(found) or 'none'}")
    backend = _ask("   " + " / ".join(names + ["none"]), found[0] if found else "none").lower()
    if backend not in names + ["none"]:
        backend = "none"

    print("\n3. The folder that holds your PDFs (subfolders are included).")
    while True:
        lib = Path(_ask("   PDF folder").strip('"').strip("'")).expanduser()
        if lib.is_dir():
            break
        print(f"   Not a folder: {lib}")

    default_data = repo / "data"
    print("\n4. Where to keep the index (about 30 MB per 100 papers). Keep it outside the PDF folder and outside")
    print("   cloud-synced folders.")
    data = Path(_ask("   index folder", str(default_data)).strip('"').strip("'")).expanduser()

    lang = _ask("\n   Board language, en (English) or zh (Chinese and English)", "en").lower()
    lang = "zh" if lang.startswith("zh") else "en"

    text = (repo / "config.example.toml").read_text(encoding="utf-8")
    import re as _re
    sub = lambda key, val, t: _re.sub(rf"(?m)^{key} = .*$", lambda m: f"{key} = {val}", t, count=1)
    text = sub("roots", f"[{_toml_path(lib)}]", text)
    text = sub("data_dir", _toml_path(data), text)
    text = sub("backend", f'"{backend}"', text)
    text = sub("language", '"Chinese"' if lang == "zh" else '"English"', text)
    text = sub("ui_language", f'"{lang}"', text)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.replace(target.with_suffix(".toml.bak"))
        print(f"\n   Previous config saved as {target.with_suffix('.toml.bak').name}")
    target.write_text(text, encoding="utf-8")
    print(f"\nSaved {target}")

    bindir = Path(sys.executable).parent
    search = bindir / ("quotesight-search.exe" if sys.platform.startswith("win") else "quotesight-search")
    print("\nTo let your coding agents search the library, add this to your CLAUDE.md or AGENTS.md:\n")
    print(f"- My PDF library is indexed. Before opening PDFs to find literature for a claim, run")
    print(f"  `\"{search}\" -c -n 8 \"<query>\"` (2 to 4 specific queries), read the passages, and cite file and page.")
    print("  See prompts/agent_instructions.md in the QuoteSight folder for the full version.\n")


def main_index(argv=None):
    ap = argparse.ArgumentParser(prog="quotesight", description="Build and maintain the quotesight-search index.")
    _common(ap)
    sub = ap.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("update", help="index new or changed PDFs, drop deleted ones, embed, fetch metadata")
    up.add_argument("paths", nargs="*", help="only these PDF files (default: whole library)")
    up.add_argument("-j", "--workers", type=int)
    up.add_argument("--no-embed", action="store_true")
    up.add_argument("--no-meta", action="store_true")
    sub.add_parser("embed", help="compute vectors for chunks that have none (resumable)")
    mp = sub.add_parser("meta", help="look up title, authors, journal and DOI on Crossref")
    mp.add_argument("--force", action="store_true")
    sub.add_parser("stats", help="index size and counts")
    sub.add_parser("errors", help="PDFs that failed, are scanned, or are duplicates")
    sub.add_parser("doctor", help="check the setup")
    sub.add_parser("setup", help="answer four questions and write config.toml")
    ip = sub.add_parser("init", help="write a starter config.toml")
    ip.add_argument("path", nargs="?", default="config.toml")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        return init_config(a.path)
    if a.cmd == "setup":
        return setup(a.config or str(config.user_config_dir() / "config.toml"))
    config.get(a.config)
    from . import core

    log = lambda m: print(m, file=sys.stderr, flush=True)
    if a.cmd == "update":
        print(json.dumps(core.update(workers=a.workers, only=a.paths or None, embed_after=not a.no_embed,
                                     meta_after=not a.no_meta, log=log)))
    elif a.cmd == "embed":
        print(core.embed(log=log))
    elif a.cmd == "meta":
        from . import meta
        print(json.dumps(meta.update_meta(force=a.force, log=log)))
    elif a.cmd == "stats":
        print(json.dumps(core.stats(), indent=1))
    elif a.cmd == "errors":
        con = core.connect()
        for r in con.execute("SELECT status, pdf_type, pages, filename, error FROM papers WHERE status != 'ok' "
                             "OR pdf_type IN ('scanned','mixed') ORDER BY status, filename"):
            print(f"{r['status']:9} {r['pdf_type'] or '-':8} pages={r['pages']} {r['filename']} {r['error'] or ''}")
    elif a.cmd == "doctor":
        doctor()


def main_app(argv=None):
    ap = argparse.ArgumentParser(prog="quotesight-app", description="Open the local search board in the browser.")
    _common(ap)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--port", type=int)
    a = ap.parse_args(argv)
    config.get(a.config)
    from . import app
    app.main(open_browser=not a.no_browser, port=a.port)


if __name__ == "__main__":
    main_search()
