# Overlay Label and Camera Orientation Design

## Goal

Make a captured result understandable from the image alone while ensuring the
live preview and analyzed result use the same left-to-right orientation.

## Overlay labels

- Every detected box always shows `NN Product name`.
- Unknown objects show `NN 알 수 없음`.
- Confidence is not shown on the image. It remains available in the result
  list.
- Confirmed boxes and labels use the existing confirmed teal; Unknown boxes
  and labels use the existing amber.
- The selected box remains thicker and is painted last so that its outline and
  label remain visible when boxes overlap.
- Labels stay inside the visible canonical image bounds and use the existing
  ellipsis behavior for unusually long names.

## Orientation

- The canonical inference image remains the EXIF-transposed RGB frame returned
  by the worker. Detection boxes remain in that canonical frame.
- The desktop camera preview must not use a mirror effect, even when the camera
  driver reports a front-facing lens.
- The captured image and overlay are not flipped after inference.
- Therefore the live preview, captured result, and overlay all show the same
  real-world left-to-right orientation.

## Verification

- Painter regression tests prove all objects receive full labels and the
  selected object is painted last and thicker.
- Camera UI tests prove front-facing preview compensation is applied and
  non-front-facing preview is unchanged.
- Existing overlay hit-testing and canonical box mapping tests continue to
  pass.
- Flutter analyze and the relevant widget/unit suites must pass.
