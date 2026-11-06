.PHONY: test fixture benchmark smoke doctor log-summary clean

test:
	python3 -m unittest discover -s tests -v

fixture:
	python3 -m benchmarks.generate_fixture --output ./.benchmark/complex-100 --files 100 --lines 1000 --force

benchmark: fixture
	python3 -m benchmarks.run_benchmark --source ./.benchmark/complex-100 --output reports/benchmark-100-files-1000-lines.json --runs 5

smoke: fixture
	python3 -m ucg.cli scan ./.benchmark/complex-100 --db ./.benchmark/smoke.sqlite

clean:
	rm -rf .benchmark .guardian __pycache__ ucg/__pycache__ benchmarks/__pycache__ tests/__pycache__


doctor:
	python3 -m ucg.cli --root . doctor

log-summary:
	python3 -m ucg.cli --root . log-summary
