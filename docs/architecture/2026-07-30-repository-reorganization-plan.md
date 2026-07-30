# Repository reorganization implementation plan

Approved on 2026-07-30.

1. Inventory every registered worktree, ref, tracked/untracked/ignored file,
   nested repository, and dangling commit.
2. Create a complete verified Git bundle plus status, patch, untracked-file,
   and file inventories outside the repository.
3. Preserve the dirty master work as focused commits.
4. Merge the divergent Flutter camera/deployment history while retaining
   canonical batch inference and timing behavior.
5. Introduce stable R&D responsibility boundaries, grouped configuration,
   immutable policies, dataset manifests, artifact verification, and suite
   policy without breaking compatibility paths.
6. Remove data-plane files from the public tree, retain local ignored copies,
   classify ignored duplicates/caches, and archive unique evidence externally.
7. Rewrite the to-be-published history to remove oversized/sensitive blobs,
   preserving authorship and source history; retain the complete original
   bundle externally.
8. Verify hermetic Python, artifact integration, Flutter, canonical and legacy
   contracts, packaging, repository policy, and a clean clone.
9. Fast-forward `master` and push to the empty GitHub repository without force.
