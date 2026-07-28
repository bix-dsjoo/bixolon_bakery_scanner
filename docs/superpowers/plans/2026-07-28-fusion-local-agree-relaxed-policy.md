# Fusion-local agreement policy implementation plan

1. Extend the immutable policy format with a versioned decision rule while
   retaining schema-v1 read compatibility.
2. Add policy and runtime tests that prove local agreement overrides the former
   risk threshold and disagreement abstains.
3. Generate the approved policy artifact from the existing B1 evidence and
   pin its SHA-256 in classifier configuration.
4. Run focused and classification regression tests, then evaluate the policy on
   the recorded evidence.
