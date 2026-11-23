.DEFAULT_GOAL := doctor
.PHONY: init doctor preview build build-pages

QUARTO ?= quarto
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
			printf '%s\n' 'For this shell, run: . /etc/sandbox-persistent.sh'; \
		else \
			printf 'For later uv commands, set: %s\n' "$$setting"; \
		fi; \
	else \
		uv sync --locked; \
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

doctor:
	@status=0; \
	uv run --locked at cms scan-secrets --workspace || status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || status=1; \
	exit $$status
