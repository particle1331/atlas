.DEFAULT_GOAL := doctor
.PHONY: doctor docs preview build

QUARTO ?= quarto
PORT ?= 4200

docs: preview

preview:
	QUARTO="$(QUARTO)" uv run at cms preview --port $(PORT)

build:
	QUARTO="$(QUARTO)" uv run at cms build

doctor:
	@doctor_status=0; \
	uv run at vault check || doctor_status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || doctor_status=1; \
	exit $$doctor_status
