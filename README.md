# ollama-chat-ui-examples

Progressive Chat UI examples for Ollama and Qwen — each stage is a
self-contained snapshot that builds on the previous one.

## Prerequisites

Pull a model (the default is `qwen3.5:9b`; change `MODEL_NAME` at the top of
any `main.py` to use a different one):

```bash
ollama pull qwen3.5:9b
```

## Install

From the repo root, install the package and all dependencies into your
virtual environment:

```bash
pip install -e .
```

Re-run this command any time you edit source files so the entry-point scripts
pick up your changes.

## Running a stage

Each stage is exposed as a console script:

| Stage | What it demonstrates | Command |
|-------|----------------------|---------|
| 1 | Agent class validated through a CLI loop | `chat-ui-stage1` |
| 2 | FastAPI server + WebSocket echo (no UI) | `chat-ui-stage2` |
| 3 | Server serves `index.html`; layout renders | `chat-ui-stage3` |
| 4 | Real streaming: thinking, content, tool calls | `chat-ui-stage4` |
| 5 | Sessions sidebar, history replay on reconnect | `chat-ui-stage5` |
| 6 | Skills picker in sidebar | `chat-ui-stage6` |
| 7 | Context warnings, compaction, slash-command buttons (final) | `chat-ui-stage7` |

Stages 2–7 start a server on `http://127.0.0.1:8000/`. Press `Ctrl+C` to stop.

Stage 1 is a CLI-only loop; type `quit` or `exit` to stop.

### Example: running stage 1 (CLI)

```
> chat-ui-stage1
--- Agent session: 2025-05-14_10-32-01 ---
Type 'quit' to exit.

You: what is the capital of France?
Assistant: The capital of France is Paris.

You: quit
```

### Example: running stage 7 (full web UI)

```
> mkdir my-session && cd my-session
> chat-ui-stage7
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Then open `http://127.0.0.1:8000/` in your browser. Running from a dedicated
folder keeps `history/` and `skills/` for that session in one place.

## Notes

- Each stage creates `history/` and `skills/` folders relative to the **working
  directory** on first run. Run each stage from a dedicated folder if you want
  sessions to stay separate.
- For stages 6 and 7, drop `.md` files into a local `skills/` folder before
  starting. Two examples are included in `stage7/skills/`.
- History files saved by one stage are not guaranteed to be compatible with
  another stage.
