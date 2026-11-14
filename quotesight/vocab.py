"""Vocabulary list: a word or phrase selected on the board, explained in context by the configured LLM backend,
saved with its sentence and the paper it came from. Stored in <data_dir>/vocab.jsonl, one entry per line."""
import json
import re
import time

from . import config, core, llm

SYSTEM = """You help a researcher whose first language is {language} learn the academic English of their field ({description}).
The user sends a selected word or phrase and the passage it was selected from. Return:
- sentence: the one sentence of the passage that contains the selection, copied verbatim (only rejoin words split by line-break hyphens, and drop citation numbers glued to words).
- lemma: the dictionary form of the selection (keep a phrase as a phrase).
- pos: part of speech in English (noun, verb, adjective, adverb, phrase...).
- meaning: the translation into {language} that fits this sentence, short. If {language} is English, a short plain-English paraphrase.
- gloss: a short English definition in this sense.
- note: one short line in {language} on usage, collocation or a field-specific sense if it helps; otherwise an empty string.
Return only the JSON object."""

SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {k: {"type": "string"} for k in ("sentence", "lemma", "pos", "meaning", "gloss", "note")},
          "required": ["sentence", "lemma", "pos", "meaning", "gloss", "note"]}


def path():
    return config.get().data_dir / "vocab.jsonl"


def _paper(pid):
    if pid is None:
        return {}
    r = core.connect().execute(
        "SELECT p.id, p.filename, COALESCE(m.title, p.title) AS title, m.authors, COALESCE(m.year, p.year) AS year, "
        "COALESCE(m.journal, p.journal) AS journal, m.doi FROM papers p LEFT JOIN meta m ON m.path=p.path WHERE p.id=?",
        (pid,)).fetchone()
    return dict(r) if r else {}


def load():
    out = []
    try:
        for line in path().read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def add(word, context, paper_id=None, page=None, language=None, emit=None):
    word = re.sub(r"\s+", " ", (word or "").strip())
    context = (context or "").strip()
    if not word or not context:
        raise ValueError("empty selection")
    cfg = config.get()
    backend = cfg["llm"]["backend"]
    call = llm.BACKENDS[backend]
    model = cfg["llm"].get(f"{backend}_vocab_model") or None
    usage, t0 = llm.Usage(), time.time()
    system = SYSTEM.format(language=language or cfg["llm"]["language"], description=cfg["library"]["description"])
    user = f"Selection: {word}\n\nPassage:\n{context[:3000]}"
    tr = (call(system, user, SCHEMA, usage, emit or (lambda e: None), model=model) if model
          else call(system, user, SCHEMA, usage, emit or (lambda e: None))) or {}
    sentence = tr.get("sentence") or ""
    for e in load():
        if e["lemma"].lower() == (tr.get("lemma") or word).lower() and e["sentence"] == sentence:
            return dict(e, duplicate=True)
    e = {"id": time.strftime("%Y%m%d-%H%M%S"), "time": time.time(), "word": word,
         "lemma": tr.get("lemma") or word, "pos": tr.get("pos", ""), "meaning": tr.get("meaning", ""),
         "gloss": tr.get("gloss", ""), "note": tr.get("note", ""), "sentence": sentence,
         "paper": _paper(paper_id), "page": page, "tokens": usage.total(), "model": usage.model,
         "seconds": round(time.time() - t0, 1)}
    with path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return e
