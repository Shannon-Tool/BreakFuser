.PHONY: install lint typecheck test e2e bench acceptance clean

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check src tests bench examples
	ruff format --check src tests bench examples

typecheck:
	mypy src/breakfuser src/BreakFuser

test:
	pytest -m 'not e2e' --cov=breakfuser --cov=BreakFuser --cov-report=term-missing --cov-report=json --cov-fail-under=85
	coverage report --include='*/breakfuser/orchestrator.py,*/breakfuser/dag.py,*/breakfuser/context.py,*/breakfuser/decider.py,*/breakfuser/voi.py,*/breakfuser/security.py,*/breakfuser/privacy.py,*/breakfuser/harvest/*' --fail-under=90

e2e:
	pytest -m e2e tests/e2e

bench:
	python -m bench.harvest.run
	python -m bench.base

acceptance: lint typecheck test e2e bench

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov build dist *.egg-info coverage.json .coverage
