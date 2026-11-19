.DEFAULT_GOAL := doctor
.PHONY: doctor preview build

QUARTO ?= quarto
PORT ?= 4200
SOURCES ?= 1

preview:
	QUARTO="$(QUARTO)" uv run at cms preview --port $(PORT) $(if $(filter 0,$(SOURCES)),--no-source-browser)

build:
	QUARTO="$(QUARTO)" uv run at cms build

doctor:
	@doctor_status=0; \
	uv run at vault check || doctor_status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || doctor_status=1; \
	exit $$doctor_status
