# Operational tools

New command implementations are grouped by responsibility:

- `artifacts/`: materialize and verify external artifacts.
- `data/`: build, validate, and version datasets.
- `train/`: launch reproducible training runs.
- `evaluate/`: accuracy and error-taxonomy evaluation.
- `benchmark/`: CPU/GPU performance protocols.
- `package/`: release and installer construction.
- `migrate/`: one-time compatibility migrations.

Existing `scripts/` paths remain compatibility entry points. When a script is
modernized, its implementation moves here and the old path becomes a thin
wrapper.
