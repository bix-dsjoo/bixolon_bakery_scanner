# Overlay consumed by the pinned MMDetection checkout; paths/sizes are injected per run.
_base_ = "../../third_party/mmdetection/configs/rtmdet/rtmdet_tiny_8xb32-300e_coco.py"
metainfo = {"classes": ("bread",)}
model = dict(bbox_head=dict(num_classes=1))
train_dataloader = dict(dataset=dict(metainfo=metainfo, ann_file="__INJECTED_TRAIN_ANNOTATIONS__"))
val_dataloader = dict(dataset=dict(metainfo=metainfo, ann_file="__INJECTED_VALIDATION_ANNOTATIONS__"))
test_dataloader = val_dataloader
# Both 640 and 768 experiments replace every resize scale deterministically.
input_size = "__INJECTED_INPUT_SIZE__"
seed = 20260724
