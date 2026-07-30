# Artifact materialization and recovery

## Storage rules

- External object storage: datasets, checkpoints, training runs, raw
  predictions, prototype/support banks, Python/CUDA runtimes, wheels, and
  installers.
- Git: code, configs, manifests, immutable policies, small synthetic fixtures,
  compact reviewed summaries.
- Git LFS: only reviewed redistribution-cleared files under
  `release-assets/models/` or `release-assets/prototype-banks/`.
- GitHub Releases: final distributable assets under 2 GiB when licensing and
  repository quota allow it; releases are not a training artifact store.

## Verification

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m bakery_scanner.artifacts.cli --manifest-only
python -m bakery_scanner.artifacts.cli
```

The first command reports local availability. The second fails closed on a
missing file, byte-size mismatch, or SHA-256 mismatch. Runtime-specific
manifests and configs perform their own stricter checks as well.

## Recovery

The pre-reorganization local repository is recoverable from the external Git
bundle and file inventory created during migration. Generated caches may be
removed only after their producer, inputs, and deterministic regeneration
command are identified. Never delete the only copy of an ignored artifact.
