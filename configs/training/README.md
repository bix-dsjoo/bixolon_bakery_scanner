# Training configuration

Training configs belong here and must declare dataset manifest, split identity,
seed, preprocessing version, initialization artifact, and output receipt path.
Generated upstream framework overlays remain in `configs/generated/`.

Never tune against `locked_acceptance` data. A completed run writes a resolved
config and hashes to `experiments/<run-id>/receipt.json`; checkpoints and logs
go to the ignored `outputs/` directory or the external artifact store.
