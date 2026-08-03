# Benchmark tools

The phase-1 RTX 5080 worker receipt uses the external manifest at
`C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\manifest.json`.
The fixed protocol performs 20 warm-ups followed by 100 observations for each
of E, M, and H, at the worker boundary
`file_read_to_in_memory_result_payload`.

Before an evidence run, verify every declared artifact ID, byte size, and
SHA-256:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path; python -m bakery_scanner.artifacts.cli --root . --lock artifacts.lock.json
```

Run the grouped CUDA receipt only after that verification succeeds:

```powershell
python scripts/benchmark_camera_worker.py --repo-root . --device cuda --manifest C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\manifest.json --protocol benchmarks/protocols/rtx5080_worker_p95_v1.json --output C:\bixolon-artifacts\bixolon_bakery_scanner\benchmarks\rtx5080_worker_p95_v1\gpu_batch_fp32_raw.json
```

Raw manifests, image paths, predictions, and timing traces remain external.
Git stores only a committed compact reviewed summary and its immutable
identities. Do not make a performance claim—including a p95 claim—without that
committed compact summary; an unavailable GPU, manifest, or artifact is
unverified rather than evidence of a result.
