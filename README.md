<div align="center">

<img src="Assets/icon-1024.png" width="120" alt="QuoteSight icon">

# QuoteSight

**See the real sentence that backs up your claim**

Type a claim; get the papers that support or refute it, the verbatim quotes, and the PDF page with each quote highlighted. Everything is indexed on your computer. Works with or without Obsidian.

![macOS](https://img.shields.io/badge/macOS-Apple_Silicon_%7C_Intel-000000?style=flat-square&logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=flat-square&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Local](https://img.shields.io/badge/index-fully_local-0A84FF?style=flat-square)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**English** · [中文](README.zh.md)

[Before you start](#before-you-start) · [Install](#install) · [Use](#use) · [How it works](#how-it-works) · [Size and speed](#size-and-speed) · [Privacy](#data-and-privacy)

</div>

<!-- screenshot: the three-column board with a highlighted quote -->

QuoteSight reads every PDF in a folder, splits the text into passages, and builds two indexes: one for keywords and one for meaning. You can search it in a local web page (the board), from the command line, or let a coding agent such as Claude Code or Codex search it for you.

- **Simple**: run one installer, answer four questions, then double-click *Start*.
- **Precise**: an optional coding agent reads the best passages and returns verbatim quotes tagged *supports*, *refutes* or *context*, and QuoteSight checks each quote against the PDF text.
- **Private**: PDFs, notes and the index stay on your computer, and your files are only read, never changed.

## Before you start

The installer asks four questions. Decide these first:

| Question | Options | If unsure |
|---|---|---|
| **1. Your system** | macOS or Windows | detected automatically |
| **2. Your coding agent** for the precise search | Claude Code, Codex, or none | the one you already use. With none, the quick search still works |
| **3. Where your PDFs are** | any folder, including its subfolders | the folder you already keep papers in. If it is inside an Obsidian vault, each PDF is linked to its note automatically |
| **4. Where to keep the index** | any folder | the default (`data` inside the QuoteSight folder). Avoid the PDF folder and cloud-synced folders |

Plan on about 3 GB of free disk space (Python packages and the embedding model) and roughly 30 MB per 100 papers for the index.

## Install

### macOS

1. **Python 3.10 or newer.** In Terminal, `python3 --version` shows the version. If it is older or missing, install Python from [python.org](https://www.python.org/downloads/) (or run `brew install python`).
2. **Get QuoteSight.** In Terminal:
   ```sh
   git clone https://github.com/ZJ-Gao/QuoteSight.git
   cd QuoteSight
   ```
   Or download the ZIP from the green *Code* button on GitHub, unzip it, and `cd` into the folder.
3. **Run the installer** and answer the four questions:
   ```sh
   ./scripts/install.sh
   ```
4. **Start**: double-click `Start.command` in the QuoteSight folder. The first run downloads the embedding model (about 550 MB) and indexes your PDFs before the board opens in your browser. Later runs only index new or changed PDFs.

> [!TIP]
> If macOS blocks `Start.command` the first time, right-click it, choose *Open*, then *Open* again.

### Windows

1. **Python 3.10 or newer.** Install it from [python.org](https://www.python.org/downloads/windows/) and tick *Add python.exe to PATH* in the installer.
2. **Get QuoteSight.** Download the ZIP from the green *Code* button on GitHub and unzip it, or with Git:
   ```powershell
   git clone https://github.com/ZJ-Gao/QuoteSight.git
   cd QuoteSight
   ```
3. **Run the installer** in PowerShell from the QuoteSight folder and answer the four questions:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```
4. **Start**: double-click `Start.bat`. The first run downloads the embedding model and indexes your PDFs before the board opens in your browser.

> [!TIP]
> With an NVIDIA graphics card, indexing is much faster if you install the CUDA build of PyTorch before step 3 ([pytorch.org](https://pytorch.org/get-started/locally/)). Without one, indexing runs on the processor, which is slower but works.

### Coding agent (optional)

For the precise search, install one of these and log in once from a terminal:
- **Claude Code**: [docs.anthropic.com/claude-code](https://docs.anthropic.com/en/docs/claude-code), then run `claude` once to log in.
- **Codex CLI**: [github.com/openai/codex](https://github.com/openai/codex), then run `codex` once to log in.

QuoteSight uses your existing login or subscription, so you need no API key.

### Let your agent install it

Prefer not to use the terminal yourself? Open Claude Code or Codex in the QuoteSight folder and paste [`prompts/setup_with_ai.md`](prompts/setup_with_ai.md). The agent asks before each step as it installs QuoteSight, goes through the setup questions with you, and builds and tests the index.

## Use

### The board

Double-click *Start* (or run `quotesight-app`), type a claim or a topic, and press Enter.

- **Left**: a short summary, then the papers, filterable by *supports*, *refutes* or *context*.
- **Middle**: the quotes from the selected paper, each with a one-line note, plus buttons to open the PDF (or, with Obsidian, the note and the PDF in Obsidian).
- **Right**: the PDF page with the quote highlighted.
- **Top bar**: the model and effort, the tokens this search used, and how much of your 5-hour and 7-day usage is left (Claude only).

Choose the search mode at the top:
- **Claude** or **Codex**: precise, with about 30 seconds and 25,000 to 46,000 tokens per search.
- **Quick**: no agent, about one to two seconds and no tokens. Instead of agent quotes, the embedding model marks the most relevant sentences.

The menu at the top left sets the theme: System, Light or Dark. Drag the dividers to resize the columns. **EN / 中英** switches the language: in 中英 mode the interface, notes and summaries are in Chinese, and the quotes stay in the original English. **History** (top left, collapsed) reopens earlier searches without using tokens. **Update index** brings the index up to date with your PDF folder (new, changed and deleted PDFs).

### From the command line

On macOS, run the commands with `.venv/bin/` in front (for example `.venv/bin/quotesight-search`); on Windows, with `.venv\Scripts\` in front.

```sh
quotesight-search -t -p "turbidity currents triggered by river floods"     # readable, grouped by paper
quotesight-search -c -n 8 "submarine fans during sea-level highstand"       # compact, for agents
quotesight-search --ask -t "hyperpycnal flows can feed deep-water fans"     # precise search with your agent
quotesight update                                                      # add new or changed PDFs
```

| Command | What it does |
|---|---|
| `quotesight setup` | answer the four questions again |
| `quotesight update` | index new or changed PDFs, drop deleted ones, fetch titles and authors |
| `quotesight doctor` | check the setup |
| `quotesight stats` / `errors` | counts and size; PDFs that failed, are scanned, or are duplicates |
| `quotesight-search [options] "query"` | `-p` group by paper, `-t` readable, `-c` compact, `-n` number of results, `-f` topic folder, `--ask` precise search |
| `quotesight-app` | open the board |

### Let your coding agents search it

At the end of setup, QuoteSight prints a short instruction with the full path to `quotesight-search`. Paste it into your `CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex), or use the longer version in [`prompts/agent_instructions.md`](prompts/agent_instructions.md). Your agents then search the index before opening PDFs. Reading ten returned passages costs about 5,000 tokens, ten to fifty times less than reading the PDFs, because each PDF page is sent as text plus an image.

## How it works

1. **Text**: each PDF is converted to Markdown page by page with [pdf-inspector](https://github.com/firecrawl/pdf-inspector), which also detects scanned pages. Every page is split into passages of about 300 words, so each passage keeps its page number. Reference lists and tables of contents are left out of searches.
2. **Duplicates**: when more than half of a PDF's passages already belong to another PDF, QuoteSight stores the paper once and lists its other file locations with it.
3. **Two indexes**: a keyword index (SQLite FTS5, BM25 ranking) for exact names and terms, and a semantic index of [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) vectors for passages that say the same thing in other words. The embedding model runs on your computer: on Apple silicon, an NVIDIA card or the processor.
4. **Search**: a query runs through both indexes, and the two rankings are merged by reciprocal rank fusion. The percentage next to a paper is its share of the scores in that result list. It is useful for comparing papers but is not a probability.
5. **Titles and authors**: QuoteSight takes a DOI from the first two pages, looks it up on [Crossref](https://www.crossref.org/) and uses the record only if its title appears in the PDF. Otherwise it falls back on Obsidian note properties or the file name.
6. **Precise search**: your coding agent turns the input into two to four specific queries, and QuoteSight runs them and hands the agent about 30 passages. The agent returns verbatim quotes, each with a stance and a note. QuoteSight then checks every quote against its passage and marks any that do not match as *unverified*. The agent receives only text and has no tools or file access. The prompts are plain Markdown in `quotesight/prompts/`, so you can adapt them to your field.
7. **Highlight**: [pdf.js](https://mozilla.github.io/pdf.js/) renders the page's text layer, and the quote is matched in it character by character, so the highlight can start and end partway through a line. In some older PDFs, the font encoding garbles the text layer, and the board then reports that it cannot highlight the page.

## Settings

Setup writes `config.toml` to `~/.config/quotesight/` on macOS or `%APPDATA%\quotesight\` on Windows. Run `quotesight setup` again to change the main choices, or edit the file directly. [`config.example.toml`](config.example.toml) explains every option, and these are the ones you are most likely to change:

- **Topic folders**: the first-level subfolders of your PDF folder become topics you can filter by. `topic_pattern` limits indexing to matching folder names.
- **Obsidian**: notes are matched to PDFs through `[[file.pdf]]` links, so Obsidian's attachment folder setting does not matter. `skip_note_prefixes` ignores index or summary notes.
- **Agent model and effort**: `claude_model`, `claude_effort`, `codex_model`, `codex_effort` (default: Sonnet, medium effort).
- **Library description**: one phrase about your field, used in the agent's prompt.

## Size and speed

Measured on an Apple silicon MacBook with 565 PDFs (4.8 GB):

| Step | Result |
|---|---|
| Text extraction | about 50 seconds for all 565 PDFs |
| Embedding (first run) | about 48 minutes; afterwards seconds per new PDF |
| Index on disk | about 160 MB for about 31,000 passages |
| Search | under 0.1 seconds on the board; Quick mode about 1 to 2 seconds with sentence marking; about 6 seconds from the command line, mostly loading the model |
| Precise search | about 30 seconds; about 27,000 tokens with Claude Sonnet, about 46,000 with Codex |

## Data and privacy

- **Local**: your PDFs, notes and index are stored only on your computer, and only your computer can reach the board (`127.0.0.1`).
- **Crossref** receives DOIs and short title text, and an email address only if you add one in the settings.
- **Precise search** sends your input and the selected passages to Anthropic or OpenAI, under your account's terms. Quick search sends nothing.
- **Data folder** (the index folder you chose): `index.sqlite` holds the index; `history/` holds every precise search. Delete the folder to start over.

## Troubleshooting

- **`'NomicBertModel' object has no attribute 'get_extended_attention_mask'`**: a newer version of `transformers` is installed. Run `.venv/bin/pip install "transformers==4.48.3" "sentence-transformers==3.4.1"` (Windows: `.venv\Scripts\pip`).
- **Search does not find a PDF**: `quotesight errors` lists scanned PDFs, which have no text layer, and PDFs that could not be read.
- **`claude` or `codex` not found**: install it, log in once in a terminal, then run `quotesight doctor`.
- **The board does not open**: another program may be using port 8765. Run `quotesight-app --port 8780`.

## Acknowledgements

| Project | Used for | License |
|---|---|---|
| [pdf-inspector](https://github.com/firecrawl/pdf-inspector) (Firecrawl) | PDF text extraction and scan detection, and the source of all indexed text | MIT |
| [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) (Nomic AI) | embedding model | Apache 2.0 |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | running the embedding model | Apache 2.0 |
| [SQLite FTS5](https://www.sqlite.org/fts5.html) | keyword index | public domain |
| [pdf.js](https://github.com/mozilla/pdf.js) (Mozilla) | PDF rendering and the text layer for highlights | Apache 2.0 |
| [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | titles, authors, journals, DOIs | open metadata |
| [FastAPI](https://github.com/fastapi/fastapi) and [Uvicorn](https://github.com/encode/uvicorn) | the local web server | MIT, BSD |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex CLI](https://github.com/openai/codex) | optional precise search | their own terms |

The character-level matching of quotes to the PDF text layer follows the selection links of the [PDF++](https://github.com/RyotaUshio/obsidian-pdf-plus) Obsidian plugin.

## License

Released under the [MIT License](LICENSE), © 2026 ZJ-Gao. The models and libraries above have their own licenses.
