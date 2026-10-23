.PHONY: doctor

doctor:
	@doctor_status=0; \
	uv run at vault check || doctor_status=1; \
	uv run pytest --cov=atlas --cov-branch --cov-report=term-missing || doctor_status=1; \
	exit $$doctor_status
