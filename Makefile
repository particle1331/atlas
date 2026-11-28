.DEFAULT_GOAL := doctor
.PHONY: init doctor preview build build-pages opencode-sbx

QUARTO ?= quarto
QUARTO_VERSION := 1.10.18
PORT ?= 4200
SOURCES ?= 1

init:
	@command -v gitleaks >/dev/null || { echo 'Install Gitleaks before running make init.' >&2; exit 1; }
	@test -x .githooks/pre-commit || { echo 'The Atlas pre-commit hook is missing or not executable.' >&2; exit 1; }
	@prefix=$$(git rev-parse --show-prefix) && test -z "$$prefix" || { echo 'Run make init from the Atlas Git root.' >&2; exit 1; }; \
	if path=$$(git config --get core.hooksPath); then \
		test "$$path" = .githooks || { echo 'A different Git hooks path is already configured; see README.md.' >&2; exit 1; }; \
	else \
		test "$$?" -eq 1 || exit 1; \
		hooks=$$(git rev-parse --git-path hooks) || exit 1; \
		for hook in "$$hooks"/* "$$hooks"/.*; do \
			case "$$hook" in *.sample) continue ;; esac; \
			if test -f "$$hook" && test -x "$$hook"; then \
				echo 'Existing Git hooks would be bypassed; see README.md.' >&2; exit 1; \
			fi; \
		done; \
	fi; \
	git config --local core.hooksPath .githooks
	@os=$$(uname -s) || exit 1; \
	if [ "$$os" = Linux ]; then \
		export UV_PROJECT_ENVIRONMENT="$$HOME/.local/share/atlas/venv"; \
		uv sync --locked || exit 1; \
		setting='export UV_PROJECT_ENVIRONMENT="$$HOME/.local/share/atlas/venv"'; \
		env_file=/etc/sandbox-persistent.sh; \
		if [ -f "$$env_file" ] && [ -w "$$env_file" ]; then \
			grep -Fxq "$$setting" "$$env_file" || printf '\n%s\n' "$$setting" >> "$$env_file" || exit 1; \
			setting='export PATH="$$HOME/.local/bin:$$PATH"'; \
			grep -Fxq "$$setting" "$$env_file" || printf '\n%s\n' "$$setting" >> "$$env_file" || exit 1; \
			printf '%s\n' 'For this shell, run: . /etc/sandbox-persistent.sh'; \
		else \
			printf 'For later uv commands, set: %s\n' "$$setting"; \
		fi; \
	else \
		uv sync --locked; \
	fi
	@set -eu; \
	if [ "$$("$(QUARTO)" --version 2>/dev/null || true)" != "$(QUARTO_VERSION)" ]; then \
		test "$(QUARTO)" = quarto || { echo 'QUARTO must provide version $(QUARTO_VERSION).' >&2; exit 1; }; \
		case "$$(uname -s)/$$(uname -m)" in \
			Linux/x86_64) platform=linux-amd64 ;; \
			Linux/aarch64|Linux/arm64) platform=linux-arm64 ;; \
			Darwin/*) platform=macos ;; \
			*) echo 'Unsupported platform; install Quarto $(QUARTO_VERSION) manually.' >&2; exit 1 ;; \
		esac; \
		tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; \
		dir="$$HOME/.local/share/atlas/quarto-$(QUARTO_VERSION)"; \
		mkdir -p "$$dir" "$$HOME/.local/bin"; \
		curl --fail --location --output "$$tmp/quarto.tar.gz" \
			"https://github.com/quarto-dev/quarto-cli/releases/download/v$(QUARTO_VERSION)/quarto-$(QUARTO_VERSION)-$$platform.tar.gz"; \
		tar -xzf "$$tmp/quarto.tar.gz" -C "$$dir" --strip-components=1; \
		test "$$("$$dir/bin/quarto" --version)" = "$(QUARTO_VERSION)"; \
		ln -sf "$$dir/bin/quarto" "$$HOME/.local/bin/quarto"; \
		printf '%s\n' 'For this shell, run: export PATH="$$HOME/.local/bin:$$PATH"'; \
	fi
	@printf '%s\n' 'Atlas setup complete. The secret-scanning pre-commit hook is enabled for this clone (.githooks).'

preview:
	QUARTO="$(QUARTO)" uv run at cms preview --port $(PORT) $(if $(filter 0,$(SOURCES)),--no-source-browser)

build:
	QUARTO="$(QUARTO)" uv run at cms build

build-pages:
	@if [ -e frontend/_site ] || [ -L frontend/_site ]; then \
		echo 'A Pages build requires a clean checkout without frontend/_site.' >&2; \
		exit 1; \
	fi
	QUARTO="$(QUARTO)" uv run --locked pytest -q tests/test_cms.py tests/test_cms_secrets.py -k 'source_browser or pages_artifact or both_render_profiles or cms_secrets'
	QUARTO="$(QUARTO)" uv run --locked at cms build --for-pages

opencode-sbx:
	sbx run -e OPENCODE_CLI_CONFIG_CONTENT='{"keybinds":{"input.select.all":"ctrl+shift+a","input.select.line.home":"none"}}' opencode-atlas .

doctor:
	@status=0; \
	uv run --locked at cms scan-secrets --workspace || status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || status=1; \
	exit $$status
