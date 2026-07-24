# Task 4 D-FINE transform-pipeline repair report

## Scope

Restored only the D-FINE overlay's pinned upstream transform pipeline.  CUDA,
device, RTMDet, split, and epoch contracts are unchanged.

## RED

Command:

```powershell
py -3.11 -m pytest tests\test_dfine.py -k "terminal_tensor or pinned_config_transforms" -q
```

Before the overlay repair this produced `4 failed`:

- both 640 and 768 overlay cases failed because `ConvertPILImage` was absent;
- both pinned-loader cases failed with `AttributeError: 'Image' object has no
  attribute 'shape'`, proving that `Resize` alone leaves a PIL image for
  `BatchImageCollateFunction`.

## GREEN

`configs/upstream/dfine_bread.yml` now preserves the pinned D-FINE train
pipeline: photometric distortion, zoom-out, IoU crop, sanitization, horizontal
flip, injected resize, final sanitization, `ConvertPILImage(float32, scale)` and
`ConvertBoxes(cxcywh, normalize)`.  Validation retains injected resize followed
by `ConvertPILImage(float32, scale)`.

Focused verification command:

```powershell
py -3.11 -m pytest tests\test_dfine.py -k "terminal_tensor or pinned_config_transforms" -q
```

Result: `4 passed`.

The test renders both 640 and 768 overlays into temporary configs, loads them
through the pinned D-FINE `YAMLConfig`, builds train and validation datasets,
and invokes a real dataset sample.  It verifies:

- train image is a scaled `torch.float32` tensor of `[3, 640, 640]` or
  `[3, 768, 768]`;
- validation image is also a tensor at the matching injected size;
- with stochastic geometry disabled only for the numerical assertion, the
  train target equals the original sample's expected normalized `cxcywh` box
  values.  The configured terminal `ConvertBoxes` is therefore exercised, not
  merely searched as text.

Relevant regression suite:

```powershell
py -3.11 -m pytest tests\test_dfine.py -q
```

Result: `18 passed in 17.85s`.
