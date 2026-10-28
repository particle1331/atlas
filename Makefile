.DEFAULT_GOAL := doctor
.PHONY: doctor preview build

QUARTO ?= quarto
PORT ?= 4200

preview:
	QUARTO="$(QUARTO)" uv run at cms preview --port $(PORT)

build:
	QUARTO="$(QUARTO)" uv run at cms build

doctor:
	@doctor_status=0; \
	uv run at vault check || doctor_status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || doctor_status=1; \
	exit $$doctor_status
