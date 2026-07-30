# Benchmarks

`protocols/` defines measurement rules, `baselines/` stores small reviewed
summaries, and `locked-manifests/` records acceptance evidence identities.
Raw profiles, overlays, predictions, and traces go to ignored `runs/`.

A performance claim requires warm end-to-end CPU measurements for fixed E/M/H
groups, per-stage timing, and conditional-DINO execution rate. An accuracy
claim requires the deterministic IoU 0.50 error taxonomy.
