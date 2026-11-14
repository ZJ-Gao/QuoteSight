# Prompt: use another model or provider for the precise search

QuoteSight ships with two backends for the precise search: Claude Code (`claude`) and Codex CLI (`codex`).

**Only switching between models of those two?** You don't need this prompt. Change `claude_model` / `claude_effort` or `codex_model` / `codex_effort` under `[llm]` in your config file (run `quotesight doctor` to see where it is).

**Want a different provider** (for example Gemini CLI, a local model through Ollama, or an API key for OpenAI, Anthropic or another service)? Paste everything below the line into Claude Code, Codex or another coding agent, started in the QuoteSight folder, and fill in the first line.

---

Add a new backend to QuoteSight for the precise search.

The provider and model I want to use:

Work in this order and show me the plan before you change any file.

1. Read `quotesight/llm.py`. The two existing backends, `call_claude` and `call_codex`, show the contract every backend follows:
   - signature `call_<name>(system, user, schema, usage, emit)`;
   - `system` is the system prompt, `user` the user message, `schema` a JSON Schema the answer must follow;
   - return the parsed JSON answer as a Python dict (use `_json_from_text` if the provider returns plain text);
   - add token counts with `usage.add({"input": ..., "cache_write": ..., "cache_read": ..., "output": ...})`, then `emit({"kind": "usage", "tokens": dict(usage.tokens)})`;
   - set `usage.model` to a short readable model name; add to `usage.cost` only if the provider reports a cost;
   - raise `RuntimeError` with a short, readable message when the call fails.
2. Write `call_<name>` for my provider, following that contract:
   - If the provider supports structured output with a JSON Schema, use it. Otherwise append the schema to the prompt and parse the answer with `_json_from_text`.
   - Give the model no tools and no file access. It must only read the text it is sent.
   - Read any API key from an environment variable (for example `GEMINI_API_KEY`). Never write a key into a file, the config, a log or the output.
   - Prefer the provider's command-line tool or its official Python package. If a package is needed, add it to `pyproject.toml` and install it into `.venv`.
3. Register the backend: add it to `BACKENDS` and give it a display name in `LABELS` in `llm.py`. The board and `quotesight setup` read this list, so nothing else needs to change for the new choice to appear.
4. Add `<name>_model` and `<name>_effort` (leave effort empty if the provider has no such setting) to the `"llm"` defaults in `quotesight/config.py` and to `[llm]` in `config.example.toml`, with one comment line each. Set `backend = "<name>"` in my own config file only if I ask.
5. Test:
   - `quotesight-search --ask -t "<a claim from my field>"` with my config set to the new backend; show me the output, the token count and the time;
   - confirm the quotes come back marked as verified (not *unverified*) for most findings;
   - open the board (`quotesight-app`) and check that the new backend appears in the search menu.
6. Tell me in two or three sentences what you changed, and how to switch back.

Rules:
- Do not change the indexing, the search ranking, the prompts in `quotesight/prompts/`, or the board's layout.
- Keep the change to `llm.py`, `config.py`, `config.example.toml` and, if needed, `pyproject.toml`.
- Do not move, rename or delete any of my PDFs or my index.
