.PHONY: verify run selftest report test lint mutants sbom
verify:
	bash scripts/verify.sh
run:
	bash scripts/run_all.sh
selftest:
	bash scripts/selftest.sh
report:
	.venv/bin/python -m ftlab.cli analyze
	.venv/bin/python -m ftlab.cli report
test:
	.venv/bin/pytest
lint:
	.venv/bin/ruff check src tests
	.venv/bin/mypy
mutants:
	python3 -P scripts/mutants.py
sbom:
	python3 -P scripts/sbom_stdlib.py --input requirements.freeze.txt --out SBOM.cdx.json --name finetune-vs-rag-lab
