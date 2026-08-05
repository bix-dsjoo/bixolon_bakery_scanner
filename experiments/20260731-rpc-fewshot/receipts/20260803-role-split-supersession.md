# Role-split supersession notice

The preliminary global-branch receipts dated 2026-08-03 were generated from
`scene_roles.json` at 09:26 KST.  At 09:34 KST, commit `17ca760` added the
canonical difficulty-balance refinement required by the experiment contract.

Re-deriving the roles from the trusted `C:\workspace\archive` source with the
current canonical splitter found 222 `val2019` image-role changes, all
burst-atomic swaps between `calibration` and `development_selection`.  The
source identity, burst identity, and difficulty remain unchanged; only the
role assignment differs.

Consequences:

- Existing DINOv3 global curves and method pilots remain preserved for audit,
  but are superseded and must not select a method, support count, gate, or
  fusion policy.
- The interrupted v1 feature-cache temporary directory and its input receipt
  are retained externally and are not reused.
- V2 scene roles and development, calibration, and locked ground-truth
  manifests are being materialized from the trusted source.  All subsequent
  feature caches, base-head artifacts, Stage-1 evidence, and locked evidence
  must bind the v2 lineage.

This is a fail-closed invalidation, not a performance or accuracy result.
