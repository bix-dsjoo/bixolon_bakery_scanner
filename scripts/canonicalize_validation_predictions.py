"""Convert per-image detector JSON into the canonical OOF proposal artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bakery_scanner.detectors.dfine import parse_dfine_output
from bakery_scanner.detectors.rtmdet import parse_rtmdet_output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("dfine", "rtmdet"), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("detector validation JSON must be a list of per-image records")
    parse = parse_dfine_output if args.backend == "dfine" else parse_rtmdet_output
    output = []
    for record in records:
        rows = parse(record["image_id"], tuple(record["image_size"]), record["labels"], record["boxes"], record["scores"], args.source)
        output.extend({"image_id": row.image_id, "source": row.source, "score": row.score, "box": [row.box.x, row.box.y, row.box.width, row.box.height]} for row in rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
