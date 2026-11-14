# Snippet: teach your coding agents to use quotesight-search

Add the block below to your global agent instructions: `~/.claude/CLAUDE.md` for Claude Code, `~/.codex/AGENTS.md` (or a project `AGENTS.md`) for Codex. Edit the library description in the first line.

---

## Literature search (quotesight-search)
- My PDF library of <describe it: field, topics> is indexed by QuoteSight. `quotesight-search "<claim or keywords>"` searches the full text of every PDF with keyword plus semantic matching.
- Use it first whenever a task needs literature that supports, refutes or enriches a claim, before opening any PDF. Read only the returned passages; open a specific PDF page only when a figure or more context is needed.
- Useful forms:
  - `quotesight-search -c -n 8 "<query>"`: compact text, each passage headed `[#chunk_id] file | topic | p.N`. Best for agents.
  - `quotesight-search -p -t "<query>"`: grouped by paper with a relevance share.
  - `-f <topic>` limits to one topic folder; `"exact phrase"` in double quotes; `--refs` also searches reference lists.
  - `quotesight-search --ask -t "<claim>"`: lets the configured LLM pick verbatim quotes with a stance. Slower and uses tokens.
- Break a broad claim into 2 to 4 specific queries (mechanism, setting, key terms and their usual synonyms) and run them in one turn.
- Judge support or contradiction yourself from the passages; the tool only ranks relevance. Quote verbatim and cite file and page.
- After adding PDFs to the library, run `quotesight update`.
