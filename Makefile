.PHONY: help setup test translate docker-build docker-test docker-build-orchestrator docker-orchestrate docker-orchestrate-test docker-e2e clean

SHELL := /bin/bash

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies and validate environment
	./scripts/setup.sh

test: ## Run integration tests
	./scripts/test-translation.sh

test-upstream: ## Run upstream bilingual_book_maker tests
	python -m pytest tests/ -v

translate: ## Interactive translation (usage: make translate BOOK=file.epub)
	@[ -n "$(BOOK)" ] || (echo "Usage: make translate BOOK=file.epub [PROFILE=lovecraft] [MODEL=opus] [LANG=de]"; exit 1)
	./scripts/translate.sh "$(BOOK)" $(if $(PROFILE),-p $(PROFILE)) $(if $(MODEL),-m $(MODEL)) $(if $(LANG),-l $(LANG))

translate-test: ## Test translation on 5 paragraphs (usage: make translate-test BOOK=file.epub)
	@[ -n "$(BOOK)" ] || (echo "Usage: make translate-test BOOK=file.epub [PROFILE=lovecraft]"; exit 1)
	./scripts/translate.sh "$(BOOK)" -t 5 $(if $(PROFILE),-p $(PROFILE))

docker-build: ## Build Docker image
	docker compose -f docker-compose.yml build

docker-test: ## Run 5-paragraph test in Docker (usage: make docker-test BOOK=books/file.epub)
	@[ -n "$(BOOK)" ] || (echo "Usage: make docker-test BOOK=books/file.epub"; exit 1)
	docker compose -f docker-compose.yml run --rm translator \
		--book_name /books/$$(basename "$(BOOK)") \
		-m 3pass-sonnet --single_translate --language de --use_context \
		--test --test_num 5

docker-build-orchestrator: ## Build orchestrator Docker image
	docker compose -f docker-compose.yml build orchestrator

docker-orchestrate: ## Run orchestrated translation (usage: make docker-orchestrate BOOK=books/file.epub)
	@[ -n "$(BOOK)" ] || (echo "Usage: make docker-orchestrate BOOK=books/file.epub [LANG=de] [MODEL=3pass-sonnet]"; exit 1)
	docker compose -f docker-compose.yml run --rm orchestrator \
		/books/$$(basename "$(BOOK)") \
		--language $(or $(LANG),de) \
		--model $(or $(MODEL),3pass-sonnet) \
		--profiles-dir /app/profiles \
		--report-dir /reports

docker-orchestrate-test: ## Test orchestrator on 10 paragraphs
	@[ -n "$(BOOK)" ] || (echo "Usage: make docker-orchestrate-test BOOK=books/file.epub"; exit 1)
	docker compose -f docker-compose.yml run --rm orchestrator \
		/books/$$(basename "$(BOOK)") \
		--language $(or $(LANG),de) \
		--model $(or $(MODEL),3pass-sonnet) \
		--profiles-dir /app/profiles \
		--report-dir /reports \
		--test-num 10

docker-e2e: ## Run E2E pipeline test in orchestrator container
	docker compose -f docker-compose.yml run --rm \
		--entrypoint python3 orchestrator test_orchestrator_e2e.py

profiles: ## List available translation profiles
	@echo "Available profiles:"
	@for f in examples/profiles/*.json; do \
		[ "$$(basename $$f)" = "_template.json" ] && continue; \
		name=$$(python3 -c "import json; print(json.load(open('$$f'))['name'])"); \
		printf "  \033[36m%-15s\033[0m %s\n" "$$(basename $$f .json)" "$$name"; \
	done

clean: ## Remove generated files and caches
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f /tmp/t.epub
