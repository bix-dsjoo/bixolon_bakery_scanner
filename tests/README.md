# Test suites

- `unit/`: hermetic logic tests.
- `contract/`: immutable pipeline, output, integrity, and repository policies.
- `classification/`, `e2e/`, `prototype/`, `deployment/`: compatibility suites
  retained while modules migrate behind stable namespaces.
- `artifact`: tests needing local models/data/runtime; excluded by default.
- `gpu`: tests needing the declared GPU; excluded by default.
- `slow`: long benchmark/package checks; excluded by default.

Run the hermetic default suite with `python -m pytest`. Run local artifact
integration with `python -m pytest -m artifact`; add `-m gpu` only on the
declared device. Never interpret a skipped artifact suite as release evidence.
