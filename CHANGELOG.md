# Changelog

Synced from the author's local build (paper-index); its `CHANGELOG.md` marks each entry as synced, pending or local-only, so the two can be compared.

## Unreleased

### Added
- **Adjust the results.** "More related papers" lists the next papers in the ranking without using tokens; "Add to results" has the model read the whole paper and label each quote supports, refutes or context. "Read more quotes" (a number, or empty for the model to decide) and "★ More important than ranked" read more quotes from one paper. (`/api/more`, `/api/addpaper`, `/api/history/{id}/boost`, `/api/history/{id}/extend`)
- **Relevance score out of 10.** Mean of 0..1 scores for whole-paper retrieval, the model's quote relevance and, after marking, Rocchio relevance feedback that leaves out a paper's own quotes. It sorts the left column, and an arrow on a card shows how far a paper moved after a change. Computed locally, no tokens. (`quotesight/rank.py`)
- **Search until the limit or until covered.** The original input is searched with the queries, the best passage of each paper that ranks high for the whole input is added, and when the quotes cover fewer papers than the limit the model writes new queries and one more round is read. (`prompts/plan_more.md`)
- **Better quote checking.** A quote split by a footnote in the text layer still verifies (threshold 0.8). A quote attached to the wrong passage is moved to the right one, and one found nowhere is dropped. Old searches are rechecked when opened.
- **Highlights on accepted manuscripts.** If the first match fails, the board matches again with digits ignored, so line numbers in the text layer no longer break the highlight.
- **Cards show citation info only.** No file name or folder; the year follows the journal.
- **Max papers and max quotes per paper.** "Max quotes" in Settings now caps relevant papers (10/15/20); a new "Max quotes per paper" (1/5/10, default 5) caps quotes per paper, ranked by relevance. The prompt states both limits and the backend trims any excess. (`llm.run(per_paper=)`, `/api/ask` takes `per`)
- **Precise and broad search.** Each backend now has two entries in the search menu. Precise (~30 s) keeps the earlier scope. Broad (~60 s) asks for 5 or 6 sub-queries for a topic, reads up to `max_passages_broad` passages (default 75), and keeps sentences from papers that only mention the topic in passing, marked low relevance. On the author's library, a topic search went from 6 to 11 papers, all of them cited in the author's manuscript on that topic, at about twice the tokens. (`llm.py`: `DEPTH`; `prompts/plan.md`, `prompts/select.md`; `/api/ask` takes `depth`)
- **At most 2 passages per paper per query.** Both depths spread the passage budget over more papers instead of letting a few papers fill it. (`core.search(max_per_paper)`)
- **Custom stance colors.** PDF bar ⋯ → Colors and opacity (or click a color in the bar with no text selected): pick the color and highlight opacity (10–60%) for supports, refutes and context, with Reset. Tags, card borders, the selection menu, the color bar and PDF highlights all follow. Saved in the browser.
- **Shortcut list in Settings.** Esc, Esc Esc, Enter, selecting PDF text, and changing colors.
- **`quotesight-search` options.** `--per-paper N` caps passages per paper in passage mode; `--broad` runs `--ask` as a broad search. With `-t`, each finding also shows its relevance.
- **Relevance and a 20-quote cap.** The LLM labels each quote high, medium or low relevance and returns at most 20 quotes (3 per paper). `max_passages` default raised from 30 to 45 so it has more to choose from. (`prompts/select.md`, `llm.py`: `SELECT_SCHEMA`, `run(max_findings)`; `/api/ask` takes `max`)
- **Settings menu.** A gear button (top left) holds theme, language, max quotes (10/15/20), minimum relevance (high/medium/low, applies at once without a new search), a shortcut-hint switch and Update index.
- **History: archive and delete.** Each saved search has a ⋯ menu. Archive moves it to an Archived list (restorable); Delete moves it to `<data_dir>/history/trash` (recoverable by hand). (`llm.py`: `move_history`; `POST /api/history/{id}/{action}`)
- **Vocabulary list.** Select a word or short phrase (up to 6 words) in a quote or on the PDF page and click "+ word": the configured backend explains it in context (dictionary form, part of speech, meaning in the board language, English definition, usage note) and saves it with its sentence and citation to `<data_dir>/vocab.jsonl`. Lookups use `claude_vocab_model` (default `haiku`, about 2k tokens) or `codex_vocab_model`. History and Vocabulary are side-by-side tabs; an open tab fills the left column. (`vocab.py`; `/api/vocab`)
- **Your own highlights.** Select text on the PDF page and click supports / refutes / context (in the selection menu or the color bar above the PDF). Highlights are drawn on the page, listed after the LLM's quotes in the middle column, and counted on paper cards. Saved in `<data_dir>/highlights.json`, keyed to the PDF path; never sent to the LLM. (`marks.py`; `/api/marks`)
- **Continuous PDF scrolling.** All pages in one scrolling column instead of prev/next buttons; only pages near the view are rendered. A bar on top shows the page number, a centered color guide (also usable as highlight buttons) and a ⋯ menu to hide it.
- **PDF++-style highlight bands.** Each highlighted line is one continuous band with a thin underline in the stance color, instead of one block per word. (`static/index.html`: `drawBands`)
- **Tighter layout.** Gaps between the HUD and columns halved (12 px to 6 px).
- **Browser icon.** The board serves a favicon (`favicon.svg`, `favicon.png`, `apple-touch-icon.png` in `static/`, routes in `app.py`), so bookmarks and tabs show the QuoteSight icon.
- **Stance-colored PDF highlights.** The highlight on the PDF page takes the color of the quote's stance (green supports, red refutes, yellow context, blue quick-mode match), semi-transparent so the text stays readable. (`static/index.html`)

### Fixed
- **Icons missing from a normal install.** `pyproject.toml` now ships `static/*.png` and `static/*.svg` with the package; before, only an editable install had the favicon files.
- **Citation numbers in quotes.** Superscript reference numbers glued to words (`landslides<sup>3,55–57</sup>`, or `mouths27,55,56` when the model drops the tags) are hidden in the board. Isotopes (`¹⁰Be`, `δ¹³C`), exponents (`s⁻¹`) and units (`km²`) are kept. The index text is unchanged. (`static/index.html`: `stripCites`)
- **Quotes marked unverified because of citation numbers.** Quote verification now ignores `<sup>`/`<sub>` tags and citation numbers, applying the same rule as the board, so a quote copied with or without its reference numbers still matches the passage. (`llm.py`: `strip_cites`, `verify`)
- **HTML in Crossref titles.** Titles are cleaned of entities and JATS markup (`&gt;` → `>`, `<scp>CT</scp>` → `CT`, `δ <sup>18</sup> O` → `δ¹⁸O`). Titles stored before this fix are cleaned the next time metadata is updated. (`meta.py`: `clean_title`)

## 2026-11-14

### Added
- **Other models and providers.** `prompts/add_model.md` walks a coding agent through adding a backend (for example Gemini, a local model through Ollama, or an API key). Backends register in `BACKENDS`/`LABELS` in `llm.py`; the board's search menu and `quotesight setup` read that list, so a new backend appears without other changes. Linked from both READMEs. (commit 8171a4c)

### Removed
- **Obsidian integration**, as it was too specific to one vault layout; README opening rewritten around the problem the tool solves. (commit 66c6f65)
