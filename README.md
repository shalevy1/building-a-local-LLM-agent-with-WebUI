# Part 2 — Runnable code per stage

Each stage is a self-contained snapshot. `cd` into the folder and run.

## Prerequisites

```bash
pip install ollama fastapi uvicorn websockets
ollama pull qwen3.5:9b   # or whichever model you want
```

The model name is set to `qwen3.5:9b` at the top of every `main.py`. Swap it
for whatever you have pulled.

## How to run each stage

| Stage | What it demonstrates | How to run |
|-------|---------------------|------------|
| 1 | The Agent class, validated through a CLI loop | `cd stage1 && python main.py` |
| 2 | FastAPI server with a WebSocket that echoes | `cd stage2 && uvicorn main:app --reload` |
| 3 | Server now serves index.html; layout renders | `cd stage3 && uvicorn main:app --reload`, open `http://localhost:8000/` |
| 4 | Real streaming: thinking, content, tool calls | `cd stage4 && uvicorn main:app --reload` |
| 5 | Sessions sidebar, history replay on reconnect | `cd stage5 && uvicorn main:app --reload` |
| 6 | Skills picker in sidebar | drop `.md` files in `stage6/skills/` first, then run |
| 7 | Slash commands as buttons (final version) | `cd stage7 && uvicorn main:app --reload` |

## Notes

- Each stage creates `history/` and `skills/` folders in its own directory on
  first run. Sessions saved in one stage do not carry over to another stage.
- Stage 1 is CLI-only and writes/reads from `stage1/history/`.
- Stages 2 through 7 serve the browser UI at `http://localhost:8000/`.
- For stage 6 and 7, drop some `.md` files in the local `skills/` folder
  before starting. Two examples are included in `stage7/skills/`.
