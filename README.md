# English Test Trainer

Local CEFR B1/B2 trainer for the Testlify "Integrated English" format: reading,
listening, writing and speaking in one page. Tasks are generated and graded by
the `claude` CLI with one shared session per run, so the examiner remembers your
recurring mistakes and never repeats topics.

## Requirements

- Python 3.12+
- [Claude Code CLI](https://claude.com/claude-code) (`claude`) available in PATH
- Chrome (Web Speech API for the speaking section, TTS voices for listening)

## Run

```bash
make up      # start server on http://localhost:8787/english-trainer.html
make down    # stop it
make logs    # tail server.log
make status  # check if running
```

Model override (defaults to your Claude Code model):

```bash
CLAUDE_ARGS="--model claude-sonnet-5" make up
```

## How it works

- `serve.py` — static files + a single `POST /api` endpoint that proxies actions
  to `claude -p` (one session per run via `--session-id`/`--resume`); the server
  is intentionally single-threaded so CLI calls serialize.
- `CLAUDE.md` — the service system prompt: the `ACTION:` protocol and JSON
  contracts (`generate_*` / `eval_*` pairs per section, plus `eval_exam`).
- `english-trainer.html` — the SPA: topic themes (corporate / general / mixed),
  practice and exam modes, two-voice TTS for dialogues, microphone speech
  recognition, prefetching of the next task, and a final examiner verdict.
