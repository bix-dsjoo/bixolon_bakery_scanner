"""Convert a labeled COCO batch into classifier evidence JSONL."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from bakery_scanner.classification.evidence import atomic_write_bytes, canonical_json_bytes, sha256_file

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--coco',type=Path,required=True); p.add_argument('--images',type=Path,required=True); p.add_argument('--role',choices=('development','locked_acceptance'),required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(argv)
    coco=json.loads(a.coco.read_text(encoding='utf-8')); images={x['id']:x for x in coco['images']}; rows=[]
    for ann in sorted(coco['annotations'],key=lambda x:x['id']):
        image=images[ann['image_id']]; path=(a.images/image['file_name']).resolve(); x,y,w,h=ann['bbox'];
        rows.append({'sample_id':f"{a.role}-{ann['id']:06d}",'capture_group':f"{a.coco.parent.parent.name}:{ann['image_id']:06d}",'image_path':str(path),'box_xyxy':[x,y,x+w,y+h],'registered':True,'sku_id':ann['category_id'],'role':a.role,'scenario_schema_version':1,'scenarios':['general']})
    atomic_write_bytes(a.output,b''.join(canonical_json_bytes(row)+b'\n' for row in rows)); return 0
if __name__=='__main__': raise SystemExit(main())
