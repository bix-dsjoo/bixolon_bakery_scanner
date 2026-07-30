# Model registry

Each `models/<artifact-id>/` directory contains a README and a versioned
manifest. Model weights are external and resolved to the manifest's expected
local filename through `artifacts.lock.json`.

Do not commit checkpoints. An approved, redistribution-cleared release model
may be placed under `release-assets/models/` and tracked with scoped Git LFS
after licensing and quota review.
