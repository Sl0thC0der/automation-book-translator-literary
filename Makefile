.PHONY: help setup test translate docker-build docker-test clean

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
