# Data control plane

Git stores catalogs, schemas, manifests, split identities, and tiny synthetic
fixtures only. Images, raw annotations, crops, embeddings, and acceptance sets
are materialized outside Git under ignored `datasets/`, `data/local/`, or an
approved object store.

Each dataset manifest records immutable counts and source annotation hashes.
Split manifests use stable sample identifiers and one of `development`,
`calibration`, or `locked_acceptance`. Moving a sample between roles creates a
new dataset/split version; it never mutates published evidence.
