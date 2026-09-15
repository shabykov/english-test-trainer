#!/usr/bin/env python3
"""English Test Trainer: static files + /api → claude CLI.

Run:   python3 serve.py
Open:  http://localhost:8787/english-trainer.html

Context and action contracts live in CLAUDE.md (picked up by the CLI automatically).

Env options:
  CLAUDE_BIN=claude             # CLI binary
  CLAUDE_ARGS="--model haiku"   # extra arguments
  PORT=8787
"""
import json
import os
import shlex
import subprocess
import time
import uuid
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT = int(os.environ.get("PORT", "8787"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_ARGS = shlex.split(os.environ.get("CLAUDE_ARGS", ""))

# One CLI session per server run: avoids repeating topics, remembers the student's errors
SESSION_ID = str(uuid.uuid4())
_session_started = False

# Per-session history: every task, answer and evaluation, one JSON per line.
# Used later to review progress and weak spots across sessions with AI.
HISTORY_DIR = Path(__file__).parent / "history"
SESSION_LOG = HISTORY_DIR / f"{time.strftime('%Y-%m-%d_%H%M%S')}_{SESSION_ID[:8]}.jsonl"


def log_history(record):
    record = {"ts": datetime.now().isoformat(timespec="seconds"), **record}
    HISTORY_DIR.mkdir(exist_ok=True)
    with SESSION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_prompt(body):
    action = body.get("action")
    mode = "assessment" if body.get("mode") == "assessment" else "training"
    head = f"ACTION: {action}\nMODE: {mode}"
    if action in ("generate_reading", "generate_listening", "generate_writing", "generate_speaking"):
        topic = str(body["topic"]).strip()
        return f"{head}\nTOPIC: {topic}"
    if action in ("eval_writing", "eval_speaking"):
        task = str(body["task"]).strip()
        answer = str(body["answer"]).strip()
        return f"{head}\nTASK: {task}\nANSWER: {answer}"
    if action in ("eval_reading", "eval_listening"):
        title = str(body.get("title", "")).strip()
        answers = json.dumps(body["answers"], ensure_ascii=False)
        return f"{head}\nTITLE: {title}\nANSWERS: {answers}"
    if action == "eval_exam":
        results = json.dumps(body["results"], ensure_ascii=False)
        return f"{head}\nRESULTS: {results}"
    return None


def validate(action, data):
    if action in ("generate_reading", "generate_listening"):
        qs = data.get("questions")
        return isinstance(qs, list) and len(qs) >= 3 and all(
            isinstance(q.get("options"), list) and len(q["options"]) == 4
            and isinstance(q.get("correct"), int) and 0 <= q["correct"] <= 3
            for q in qs
        ) and data.get("passage" if action == "generate_reading" else "script")
    if action == "generate_writing":
        return isinstance(data.get("task"), str) and isinstance(data.get("min_words"), int)
    if action == "generate_speaking":
        return isinstance(data.get("question"), str)
    if action in ("eval_reading", "eval_listening"):
        return isinstance(data.get("feedback"), str)
    if action == "eval_exam":
        return isinstance(data.get("cefr"), str) and isinstance(data.get("summary"), str)
    return isinstance(data.get("cefr"), str) and isinstance(data.get("score"), (int, float))


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # the trainer is edited live — never let the browser cache a stale page
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        global _session_started
        if self.path != "/api":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            prompt = build_prompt(body)
            if prompt is None:
                raise ValueError
        except (json.JSONDecodeError, KeyError, ValueError):
            self._json(400, {"error": "expected JSON: {action, topic | task+answer | title+answers | results}"})
            return

        session_args = (
            ["--resume", SESSION_ID] if _session_started else ["--session-id", SESSION_ID]
        )
        try:
            proc = subprocess.run(
                [CLAUDE_BIN, "-p", prompt, *session_args, *CLAUDE_ARGS],
                capture_output=True,
                text=True,
                timeout=180,
            )
        except FileNotFoundError:
            self._json(502, {"error": f"'{CLAUDE_BIN}' not found in PATH"})
            return
        except subprocess.TimeoutExpired:
            self._json(504, {"error": "claude CLI did not respond within 180 seconds"})
            return

        if proc.returncode != 0:
            self._json(502, {"error": "claude CLI: " + proc.stderr.strip()[:300]})
            return
        _session_started = True

        raw = proc.stdout.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            self._json(502, {"error": "no JSON in the CLI response", "raw": raw[:500]})
            return
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            self._json(502, {"error": "failed to parse JSON from the CLI response", "raw": raw[:500]})
            return
        if not validate(body["action"], data):
            self._json(502, {"error": "CLI response violates the contract", "raw": raw[:500]})
            return

        log_history({
            "action": body["action"],
            "mode": "assessment" if body.get("mode") == "assessment" else "training",
            "request": {k: v for k, v in body.items() if k not in ("action", "mode")},
            "response": data,
        })
        self._json(200, data)

    def _json(self, code, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        if args and "/api" in str(args[0]):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    print(f"English trainer → http://localhost:{PORT}/english-trainer.html")
    print(f"AI: {CLAUDE_BIN} -p … {' '.join(CLAUDE_ARGS)}")
    print(f"Session: {SESSION_ID} (shared memory until the server restarts)")
    print(f"History: {SESSION_LOG.relative_to(Path(__file__).parent)}")
    log_history({"event": "session_start", "session_id": SESSION_ID, "claude_args": CLAUDE_ARGS})
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
