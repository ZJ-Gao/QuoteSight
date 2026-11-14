# Prompt: set up QuoteSight with an AI coding agent

Paste everything below the line into Claude Code, Codex CLI or another coding agent, started in the QuoteSight folder. Fill in the answers at the top first, or leave them blank and the agent will ask.

---

Set up QuoteSight from this folder on my computer. Show me each command before you run anything that installs software or writes outside this folder.

My answers (ask me for any that are blank):
- Coding agent for the precise search (claude, codex or none):
- Folder that holds my PDFs:
- Folder for the index (blank = `data` inside this folder):
- Board language (en, or zh for Chinese and English):

Steps:
1. Detect the system (macOS or Windows) and check that Python 3.10 or newer is installed. If not, tell me how to install it and stop.
2. Install into `.venv` in this folder: on macOS `python3 -m venv .venv` then `.venv/bin/python -m pip install -e .`; on Windows `py -m venv .venv` then `.venv\Scripts\python.exe -m pip install -e .`. On Windows with an NVIDIA GPU, offer to install the CUDA build of PyTorch first.
3. Run `quotesight setup` from `.venv` and give it my answers.
4. List the first two levels of folder names in my PDF folder (names only, no file contents). If some first-level folders are not topics, propose a `topic_pattern` for the config file that setup printed, and ask me before changing it.
5. Run `quotesight doctor` and fix anything marked MISSING.
6. Run `quotesight update`. The first run downloads the embedding model (about 550 MB); expect several minutes per 100 papers for the vectors on a laptop. Report `quotesight stats` and anything listed by `quotesight errors`.
7. Test `quotesight-search -t -p "<a topic from my library>"`, and, if I chose an agent, `quotesight-search --ask -t "<a claim from my field>"`. Show me the output.
8. Offer to add the instruction that setup printed (or `prompts/agent_instructions.md`) to my global `CLAUDE.md` or `AGENTS.md`. Show me the text before writing it.
9. Tell me to double-click `Start.command` (macOS) or `Start.bat` (Windows) to update the index and open the board.

Do not move, rename or delete any of my PDFs. QuoteSight only reads them.
