# ADR 0001: Separate Git control plane from artifact data plane

- Status: accepted
- Date: 2026-07-30

## Context

The repository accumulated more than 14 GB of tracked datasets, checkpoints,
training outputs, duplicate samples, and a 3.4 GB wheel. Its Git object store
exceeded 11 GB, normal GitHub file and push limits, and clean-clone
reproducibility depended on local ignored files.

## Decision

Git stores source, configuration, manifests, policies, small fixtures, and
reviewed summaries. Large or sensitive assets live externally and are pinned
by `artifacts.lock.json` plus component manifests. LFS is scoped to reviewed
release assets only. Public history is rewritten before its first remote push
to remove historical data-plane blobs; the complete original history remains
in an external verified bundle.

## Consequences

Hermetic tests run from a clean clone. Artifact/GPU/slow suites are explicit
and cannot be mistaken for a passed release gate. Researchers must materialize
hash-pinned assets before full evaluation, but cloning and reviewing the
control plane remains fast and safe.
