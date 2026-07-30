# Orin GPU Batch2 Parity Benchmark Design

## Goal

Produce a GPU report for the fixed nine Batch2 images that is directly
comparable with the existing CPU `report.json`, without changing the canonical
CPU inference path, model artifacts, calibration, or fail-closed acceptance
policy.

## Baseline contract

The supplied CPU baseline uses `schema_version: 1` and evaluates exactly these
nine images in their prescribed order: three E, three M, and three H images.
It performs a one-image detector/classifier warm-up, then measures detector and
serial classifier time per image. Canonical-image loading, evaluation matching,
overlay generation, and report writing are outside the measured interval.

The baseline report records:

- `device: "CPU"`;
- the RF-DETR artifact id and immutable fusion decision rule;
- deterministic IoU-0.50 object metrics; and
- per-image and E/M/H mean end-to-end times.

Its quality result is 27 ground-truth objects, 27 predictions, 0 FP, 0 FN,
Top-1 26/27, Top-3 27/27. The non-accepted SKU-4 instance in
`g20_b02_m_0307.jpg` is explicitly `Unknown` by
`fusion_global_consensus_margin`.

## GPU parity runner

Create a non-portable Jetson runner at
`scripts/run_gpu_rfdetr_fusion.py`. It must use the same fixed sample resolver,
ground-truth source, RF-DETR-L manifest threshold, classifier policy file,
artifact integrity checks, canonical RGB preprocessing, IoU matching, and
overlay rendering as the CPU runner. It must keep the CPU runner and all
portable CPU smoke files unchanged.

The only inference-runtime difference is the explicit `CUDA:0` device. The
runner keeps FP32 execution and preserves the same direct RepViT decision gate,
conditional DINOv3 global/local evidence, immutable fusion rule, and
fail-closed `Unknown` outcome. It must never substitute a registered SKU after
a rejected direct or fusion decision.

The runner performs exactly the same one-image warm-up sequence as the CPU
baseline, then measures each of the nine images once. Its `report.json` remains
schema-version 1 and has the same `profiles`, `metrics`, and `images` fields as
the CPU report; it records `device: "CUDA:0"`. An adjacent `environment.json`
records the Jetson model, JetPack/L4T release, Python, PyTorch, CUDA, compute
capability, model/config hashes, power mode, and timestamp. A `tegrastats.log`
is retained beside the report, not folded into latency values.

Create `scripts/compare_batch2_reports.py` as a read-only report comparator.
It accepts `--cpu-report`, `--gpu-report`, and `--output`; it does not rerun
inference or modify either source report.

## Runtime admission

GPU measurement is fail-closed. Before any model is loaded, the Jetson runner
must require all of the following:

- an available CUDA device named Orin with compute capability `(8, 7)`;
- a Python 3.11 runtime, matching the repository's declared runtime range;
- a PyTorch version in the repository's declared `>=2.8,<2.9` range; and
- a PyTorch CUDA build whose compiled architecture list explicitly includes
  `sm_87`.

The currently installed Python 3.12 / PyTorch 2.13 CUDA 13.2 environment is a
raw-GPU diagnostic environment only. It emits an `sm_87` support warning and is
therefore rejected for pipeline evaluation. A compatible isolated Jetson
environment is an explicit deployment prerequisite: the runner must not try to
download, upgrade, or build it. The runner instead stops before inference with
the failed admission fields in `environment.json`.

## Comparison and acceptance

The GPU report is a measurement artifact, not a CPU-pipeline replacement or a
release acceptance result. A speed comparison is valid only when the GPU report
uses the nine expected filenames in order and matches the CPU baseline's object
counts, FP, FN, Top-1, Top-3, and fail-closed Unknown behavior. Otherwise the
report must be retained as a failed parity run with its measured timings and
reason, and no speed-improvement claim may be made.

`scripts/compare_batch2_reports.py` must show CPU and GPU per-image latency,
E/M/H means, absolute delta, relative speedup, metrics, and any decision/box
mismatch. It must identify the two host environments rather than treating their
latencies as the same-machine result.

## Verification

Unit tests must cover fixed image ordering, GPU runtime admission/rejection,
schema-1 report compatibility, preservation of `Unknown`, and a comparison
report that rejects mismatched inputs or quality metrics. Integration execution
on the Orin must retain the complete GPU report, environment receipt, and
`tegrastats` log. The existing CPU tests and portable CPU package verification
must remain unchanged and pass.
