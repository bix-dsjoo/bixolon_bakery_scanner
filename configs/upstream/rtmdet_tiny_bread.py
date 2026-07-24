# Overlay consumed by the pinned MMDetection checkout; paths/sizes are injected per run.
_base_ = "../../third_party/mmdetection/configs/rtmdet/rtmdet_tiny_8xb32-300e_coco.py"
metainfo = {"classes": ("bread",)}
model = dict(bbox_head=dict(num_classes=1))
train_dataloader = dict(dataset=dict(metainfo=metainfo, ann_file="__INJECTED_TRAIN_ANNOTATIONS__"))
val_dataloader = dict(dataset=dict(metainfo=metainfo, ann_file="__INJECTED_VALIDATION_ANNOTATIONS__"))
test_dataloader = val_dataloader
# All train/test/TTA resize scales are injected as either 640 or 768.
input_size = __INJECTED_INPUT_SIZE__
train_pipeline = [dict(type="LoadImageFromFile"), dict(type="LoadAnnotations", with_bbox=True), dict(type="Resize", scale=(input_size, input_size), keep_ratio=True)]
test_pipeline = [dict(type="LoadImageFromFile"), dict(type="Resize", scale=(input_size, input_size), keep_ratio=True)]
tta_pipeline = [dict(type="TestTimeAug", transforms=[[dict(type="Resize", scale=(input_size, input_size), keep_ratio=True)]])]
train_dataloader.update(dataset=dict(pipeline=train_pipeline))
val_dataloader.update(dataset=dict(pipeline=test_pipeline))
test_dataloader = val_dataloader
seed = 20260724
