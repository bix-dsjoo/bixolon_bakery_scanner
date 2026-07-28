# GPU batch profiling only. This file is not an OOF training configuration.
_base_ = r"C:/workspace/bixolon_bakery_scanner/third_party/mmdetection/configs/rtmdet/rtmdet_tiny_8xb32-300e_coco.py"
metainfo = {"classes": ("bread",)}
model = dict(bbox_head=dict(num_classes=1))
data_root = r"C:/workspace/bixolon_bakery_scanner/artifacts/box_system/staged/"
train_annotation = r"C:/workspace/bixolon_bakery_scanner/artifacts/box_system/interrupted-runs/dfine_n_640-seed20260724-fold0-oversized-batch-20260727T0828/fold-data/train.json"
validation_annotation = r"C:/workspace/bixolon_bakery_scanner/artifacts/box_system/interrupted-runs/dfine_n_640-seed20260724-fold0-oversized-batch-20260727T0828/fold-data/validation.json"
input_size = 768
train_pipeline = [
    dict(type="LoadImageFromFile"),
    dict(type="LoadAnnotations", with_bbox=True),
    dict(type="Resize", scale=(input_size, input_size), keep_ratio=True),
    dict(type="PackDetInputs"),
]
test_pipeline = [
    dict(type="LoadImageFromFile"),
    dict(type="Resize", scale=(input_size, input_size), keep_ratio=True),
    dict(type="PackDetInputs", meta_keys=("img_id", "img_path", "ori_shape", "img_shape", "scale_factor")),
]
train_dataloader = dict(batch_size=8, num_workers=4, dataset=dict(metainfo=metainfo, data_root=data_root, ann_file=train_annotation, data_prefix=dict(img="images/"), pipeline=train_pipeline))
val_dataloader = dict(batch_size=4, num_workers=4, dataset=dict(metainfo=metainfo, data_root=data_root, ann_file=validation_annotation, data_prefix=dict(img="images/"), pipeline=test_pipeline))
test_dataloader = val_dataloader
val_evaluator = dict(ann_file=validation_annotation)
test_evaluator = dict(ann_file=validation_annotation)
base_lr = 0.000125
optim_wrapper = dict(optimizer=dict(lr=base_lr))
param_scheduler = []
train_cfg = dict(max_epochs=1, val_interval=1)
default_hooks = dict(checkpoint=dict(type="CheckpointHook", interval=1, max_keep_ckpts=1, save_best="coco/bbox_mAP", rule="greater"))
custom_hooks = [dict(type="EMAHook", ema_type="ExpMomentumEMA", momentum=0.0002, update_buffers=True, priority=49)]
randomness = dict(seed=20260724)
