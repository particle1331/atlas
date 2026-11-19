.DEFAULT_GOAL := doctor
.PHONY: doctor preview build build-pages

QUARTO ?= quarto
PORT ?= 4200
SOURCES ?= 1

preview:
	QUARTO="$(QUARTO)" uv run at cms preview --port $(PORT) $(if $(filter 0,$(SOURCES)),--no-source-browser)

build:
	QUARTO="$(QUARTO)" uv run at cms build

build-pages:
	@if [ -e frontend/_site ] || [ -L frontend/_site ]; then \
		echo 'A Pages build requires a clean checkout without frontend/_site.' >&2; \
		exit 1; \
	fi
	QUARTO="$(QUARTO)" uv run --locked pytest -q tests/test_cms.py -k 'source_browser or pages_artifact or both_render_profiles'
	QUARTO="$(QUARTO)" uv run --locked at cms build --for-pages

doctor:
	@doctor_status=0; \
	uv run at vault check || doctor_status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || doctor_status=1; \
	exit $$doctor_status
