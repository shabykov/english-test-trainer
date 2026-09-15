PORT ?= 8787
LOG  ?= server.log

.PHONY: up down logs status

up: ## restart the server in the background
	@lsof -ti tcp:$(PORT) | xargs kill 2>/dev/null || true
	@sleep 1
	@nohup python3 serve.py > $(LOG) 2>&1 &
	@sleep 1
	@echo "up → http://localhost:$(PORT)/english-trainer.html  (log: $(LOG))"

down: ## stop the server
	@lsof -ti tcp:$(PORT) | xargs kill 2>/dev/null && echo "down" || echo "nothing running on :$(PORT)"

logs: ## tail the server log
	@tail -f $(LOG)

status: ## is the server running?
	@lsof -ti tcp:$(PORT) >/dev/null 2>&1 && echo "running on :$(PORT)" || echo "not running"
