"""Build per-SKU RepViT penultimate-feature prototypes from training sources."""
from __future__ import annotations
import argparse, hashlib
from collections import defaultdict
from pathlib import Path
import torch
import torch.nn.functional as functional
from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.repvit import RepVitM1Runner
from bakery_scanner.classification.evidence import sha256_file
from bakery_scanner.data.preprocess import load_canonical_image

ROOTS=(Path('datasets/classification/base_15class'),Path('datasets/classification/incremental_5class_crop'))

def _sku(directory: Path) -> int:
    return int(directory.name.split('_',2)[1])

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--config',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(argv)
    cfg=ClassifierConfig.load(a.config); runner=RepVitM1Runner.load(cfg); rows=defaultdict(list); hashes=[]
    with torch.inference_mode():
        for root in ROOTS:
            for directory in sorted(x for x in root.iterdir() if x.is_dir()):
                sku=_sku(directory)
                for path in sorted(x for x in directory.rglob('*') if x.is_file()):
                    image=load_canonical_image(path).image
                    feature=runner.model.forward_features(runner.transform(image).unsqueeze(0).to(runner.device)).mean(dim=(2,3))[0]
                    rows[sku].append(functional.normalize(feature,dim=0).cpu()); hashes.append(sha256_file(path))
    if tuple(sorted(rows))!=tuple(range(1,21)): raise ValueError('all 20 SKU sources are required')
    prototypes=torch.stack([functional.normalize(torch.stack(rows[sku]).mean(dim=0),dim=0) for sku in range(1,21)]).float()
    payload={'artifact_type':'repvit_m1_15plus5_feature_prototypes','schema_version':1,'checkpoint_sha256':cfg.repvit.checkpoint_sha256,'preprocess_sha256':preprocess_sha256(cfg.preprocess),'source_sha256':hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest(),'counts':{sku:len(rows[sku]) for sku in range(1,21)},'prototypes':prototypes}
    a.output.parent.mkdir(parents=True,exist_ok=True); torch.save(payload,a.output); return 0
if __name__=='__main__': raise SystemExit(main())
