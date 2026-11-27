SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nThalam - make targets\n\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: sync
sync: ## Install exactly what uv.lock says into .venv (what CI uses)
	uv sync --locked --all-extras

.PHONY: lint
lint: ## ruff + mypy --strict (SPEC-001-R4)
	uv run ruff check services scripts infra migrations
	uv run mypy services scripts/dev scripts/ops scripts/tracking infra/modules/azure-guardrails

.PHONY: test
test: ## pytest, then the spec coverage table (SPEC-001-R8)
	uv run pytest -q
	uv run python scripts/dev/spec_coverage.py

.PHONY: hooks
hooks: ## Install the pre-commit and commit-msg hooks
	bash scripts/dev/install-hooks.sh

.PHONY: secrets-scan
secrets-scan: ## gitleaks over the whole history
	@command -v gitleaks >/dev/null || { echo "gitleaks is not installed (see docs/labs/00-foundations.md)"; exit 1; }
	gitleaks git --config .gitleaks.toml --redact --no-banner .

.PHONY: sandboxes
sandboxes: ## Prove read-only access to every sandbox (reads .env; SPEC-001-R10..R13)
	uv run python scripts/dev/check_sandboxes.py

.PHONY: db-up
db-up: ## Start Postgres in Docker on 127.0.0.1 (SPEC-002-R1; compose reads .env)
	docker compose up -d --wait postgres

.PHONY: db-down
db-down: ## Stop Postgres; its data volume stays (docker compose down -v would drop it)
	docker compose down

.PHONY: migrate
migrate: ## Apply the migrations as the owner, then run `make db-roles` (SPEC-002-R2)
	uv run alembic upgrade head

# ─── Azure guardrails (ADR-0014). Nothing below reads .env as shell; see scripts/ops/tf.py ───

.PHONY: guardrails-plan
guardrails-plan: ## Plan the Azure guardrails with Terraform; changes nothing (SPEC-001-R15, R16)
	uv run python scripts/ops/tf.py plan

.PHONY: guardrails-apply
guardrails-apply: ## Apply the saved plan; CREATES Azure resources (Roshan's go)
	uv run python scripts/ops/tf.py apply

.PHONY: foundry-up
foundry-up: ## Create the Claude deployment, only if every guardrail holds (SPEC-001-R14)
	uv run python scripts/ops/foundry_park.py up

.PHONY: foundry-down
foundry-down: ## Park it: delete every deployment on the Foundry account (SPEC-001-R14)
	uv run python scripts/ops/foundry_park.py down

.PHONY: foundry-status
foundry-status: ## Up or parked
	uv run python scripts/ops/foundry_park.py status

.PHONY: azure-sweep
azure-sweep: ## Read-only exit gate: fails on anything billable left behind (SPEC-001-R17)
	uv run python scripts/ops/azure_sweep.py $(ARGS)

# ─── The dashboard: a generated mirror of the repo (Definition of Done item 9) ───

.PHONY: dashboard
dashboard: ## Rebuild docs/dashboard.html from ROADMAP.md, specs, labs, ADRs, git and saved copies
	uv run python scripts/tracking/dashboard.py

.PHONY: dashboard-azure
dashboard-azure: ## Read this month's spend and the deployment's state again (read-only), then rebuild
	uv run python scripts/tracking/dashboard.py --azure
