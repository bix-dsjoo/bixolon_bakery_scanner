# Overlay consumed by the pinned MMDetection checkout; paths/sizes are injected per run.
_base_ = r"__INJECTED_MMD_BASE__"
metainfo = {"classes": ("bread",)}
model = dict(bbox_head=dict(num_classes=1))
train_dataloader = dict(batch_size=__INJECTED_RTMDET_TRAIN_BATCH__, dataset=dict(metainfo=metainfo, data_root=r"__INJECTED_DATA_ROOT__", ann_file=r"__INJECTED_TRAIN_ANNOTATIONS__", data_prefix=dict(img="images/")))
val_dataloader = dict(batch_size=__INJECTED_RTMDET_VAL_BATCH__, dataset=dict(metainfo=metainfo, data_root=r"__INJECTED_DATA_ROOT__", ann_file=r"__INJECTED_VALIDATION_ANNOTATIONS__", data_prefix=dict(img="images/")))
test_dataloader = dict(batch_size=__INJECTED_RTMDET_TEST_BATCH__, dataset=dict(metainfo=metainfo, data_root=r"__INJECTED_DATA_ROOT__", ann_file=r"__INJECTED_VALIDATION_ANNOTATIONS__", data_prefix=dict(img="images/")))
val_evaluator = dict(ann_file=r"__INJECTED_VALIDATION_ANNOTATIONS__")
test_evaluator = dict(ann_file=r"__INJECTED_VALIDATION_ANNOTATIONS__")
default_hooks = dict(checkpoint=dict(type="CheckpointHook", interval=1, save_best="coco/bbox_mAP", rule="greater", max_keep_ckpts=1))
# All train/test/TTA resize scales are injected as either 640 or 768.
input_size = __INJECTED_INPUT_SIZE__
train_pipeline = [dict(type="LoadImageFromFile"), dict(type="LoadAnnotations", with_bbox=True), dict(type="Resize", scale=(input_size, input_size), keep_ratio=True), dict(type="PackDetInputs")]
test_pipeline = [dict(type="LoadImageFromFile"), dict(type="Resize", scale=(input_size, input_size), keep_ratio=True), dict(type="PackDetInputs", meta_keys=("img_id", "img_path", "ori_shape", "img_shape", "scale_factor"))]
tta_pipeline = [dict(type="TestTimeAug", transforms=[[dict(type="Resize", scale=(input_size, input_size), keep_ratio=True)]])]
train_dataloader.update(dataset=dict(pipeline=train_pipeline))
val_dataloader.update(dataset=dict(pipeline=test_pipeline))
test_dataloader.update(dataset=dict(pipeline=test_pipeline))
seed = 20260724
# The 8x32 upstream recipe has a global batch of 256. Each generated run
# declares its own single-GPU batch and its linearly scaled learning rate.
base_lr = __INJECTED_RTMDET_BASE_LR__
optim_wrapper = dict(optimizer=dict(lr=base_lr))
param_scheduler = [
    dict(type="LinearLR", start_factor=1.0e-5, by_epoch=False, begin=0, end=1000),
    dict(type="CosineAnnealingLR", eta_min=base_lr * 0.05, begin=150, end=300, T_max=150, by_epoch=True, convert_to_iter_based=True),
]
# Our small-data pipeline intentionally has no late 640-pixel augmentation
# switch. This prevents a 768 experiment from silently training its last
# epochs at 640 and leaves EMA enabled.
custom_hooks = [dict(type="EMAHook", ema_type="ExpMomentumEMA", momentum=0.0002, update_buffers=True, priority=49)]
