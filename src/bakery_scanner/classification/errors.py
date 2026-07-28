"""Explicit recoverable errors shared by classifier runtime stages."""

from __future__ import annotations

import re


_FAILURE_CODE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class DinoInferenceError(RuntimeError):
    """An explicitly classified, recoverable DINOv3 inference failure."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        if not isinstance(code, str) or not _FAILURE_CODE.fullmatch(code):
            raise ValueError("DINO inference failure code must be snake_case")
        super().__init__(detail or code)
        self.code = code
