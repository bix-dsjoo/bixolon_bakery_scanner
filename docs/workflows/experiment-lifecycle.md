# Reproducible experiment lifecycle

1. State one hypothesis in `experiments/<id>/experiment.yaml`.
2. Pin pipeline config, dataset manifest, split manifest, seed, preprocessing,
   initialization artifact hashes, environment, and code commit.
3. Materialize artifacts with an approved external URI; run
   `bakery-artifacts` before starting.
4. Train or collect evidence only on the declared development role.
5. Select thresholds/policies only on calibration data.
6. Freeze the candidate and evaluate once on locked acceptance data.
7. Record deterministic IoU 0.50 accuracy taxonomy and warmed CPU E/M/H
   performance separately.
8. Compare against a reviewed baseline. A claim must cite the result receipt.
9. Promote by creating new immutable model and policy manifests, then package
   from an allowlist and runtime lock.

If locked evidence influences a model, threshold, preprocessing, or policy
choice, that lock is retired. Validation requires a newly locked set.
