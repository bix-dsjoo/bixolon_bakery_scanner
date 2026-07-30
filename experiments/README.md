# Experiment lifecycle

Create `experiments/<YYYYMMDD>-<slug>/` from `template/`. Commit the question,
resolved config, receipt, and compact conclusions. Keep checkpoints, caches,
full predictions, and rendered outputs under ignored `outputs/` or in the
external artifact store.

Promotion is evidence-driven: experiment → calibration → locked acceptance →
baseline comparison → versioned model/policy manifest → deployment package.
