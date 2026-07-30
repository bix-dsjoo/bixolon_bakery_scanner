# Configuration ownership

Configuration is grouped by the operation it controls:

- `pipelines/`: versioned end-to-end compositions and immutable decision order.
- `data/`: dataset identities and local materialization contracts.
- `training/`: training defaults; every run copies resolved values into its receipt.
- `evaluation/`: matching, error taxonomy, and acceptance protocols.
- `deployment/`: package/runtime profiles.
- `generated/`: deterministic generated upstream overlays retained for compatibility.

Existing root-level YAML files are compatibility entry points. New automation
should start from `configs/pipelines/canonical_cpu.yaml` and follow its
references. Paths in pipeline composition files are repository-relative.
