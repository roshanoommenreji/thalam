SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nThalam — make targets\n\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: sync
sync: ## Install exactly what uv.lock says into .venv (what CI uses)
	uv sync --locked --all-extras

.PHONY: lint
lint: ## ruff + mypy --strict (SPEC-001-R4)
	ruff check services scripts
	mypy services scripts/dev

.PHONY: test
test: ## pytest, then the spec coverage table (SPEC-001-R8)
	pytest -q
	python scripts/dev/spec_coverage.py

.PHONY: hooks
hooks: ## Install the pre-commit and commit-msg hooks
	bash scripts/dev/install-hooks.sh

.PHONY: secrets-scan
secrets-scan: ## gitleaks over the whole history
	gitleaks git --config .gitleaks.toml --redact --no-banner .

.PHONY: sandboxes
sandboxes: ## Prove read-only access to every sandbox (reads .env; SPEC-001-R10..R13)
	python scripts/dev/check_sandboxes.py
