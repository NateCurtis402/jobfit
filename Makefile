PY      := .venv/bin/python
PIP     := .venv/bin/pip
COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help venv up down logs psql init ingest query stats gap eval label api api-install api-logs test lint fmt refresh clean

help:  ## show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /  - /'

venv:  ## create .venv and install deps (editable + dev)
	python3 -m venv .venv
	$(PIP) install -q -U pip
	$(PIP) install -q -e ".[dev]"

up:  ## start Postgres+pgvector and wait until healthy
	$(COMPOSE) up -d --wait db

down:  ## stop the stack (keeps the data volume)
	$(COMPOSE) down

logs:  ## tail db logs
	$(COMPOSE) logs -f db

psql:  ## open a psql shell on the jobfit database
	$(COMPOSE) exec db psql -U jobfit -d jobfit

init:  ## (re)apply db/init.sql to a running db
	$(COMPOSE) exec -T db psql -U jobfit -d jobfit -v ON_ERROR_STOP=1 < db/init.sql

ingest:  ## embed any unembedded postings from data/snapshot/*.json
	$(PY) -m jobfit.cli ingest

refresh:  ## re-fetch live boards into data/snapshot/ (network)
	$(PY) scripts/build_snapshot.py

query:  ## semantic search: make query q="python etl pipeline"
	$(PY) -m jobfit.cli query "$(q)" -k $(or $(k),5)

gap:  ## skills a goal role wants that your resume lacks: make gap target="AI Engineer" resume=path.pdf
	$(PY) -m jobfit.cli gap "$(target)" --resume "$(resume)" -k $(or $(k),15)

stats:  ## corpus counts: postings, embedded, sources
	$(PY) -m jobfit.cli stats

api:  ## run the API in the foreground (dev): http://localhost:8000/docs
	$(PY) -m uvicorn jobfit.api:app --host 0.0.0.0 --port 8000 --reload

api-install:  ## install + start the API as a user service (survives logout)
	cp deploy/jobfit-api.service ~/.config/systemd/user/jobfit-api.service
	systemctl --user daemon-reload
	systemctl --user enable --now jobfit-api.service
	@sleep 2 && systemctl --user --no-pager status jobfit-api.service | head -12

api-logs:  ## follow the API service log
	journalctl --user -u jobfit-api.service -f

eval:  ## score retrieval against hand labels (hit@5 / hit@10 / MRR per mode)
	$(PY) -m jobfit.cli eval --labels $(or $(labels),evals/labels.json)

label:  ## label query -> relevant postings, interactively
	$(PY) -m jobfit.cli label --queries evals/queries.txt --labels $(or $(labels),evals/labels.json)

test:  ## run the test suite
	$(PY) -m pytest -q

lint:  ## ruff check
	$(PY) -m ruff check src tests

fmt:  ## ruff format + autofix
	$(PY) -m ruff format src tests && $(PY) -m ruff check --fix src tests

clean:  ## remove caches (keeps the db volume)
	rm -rf .pytest_cache .ruff_cache **/__pycache__
