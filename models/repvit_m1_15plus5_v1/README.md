# RepViT-M1 15+5 v1

20-SKU bakery product classifier. This is a RepViT-M1 model expanded from an
existing 15-SKU model with five additional SKUs (4, 6, 9, 15, and 16).

## Files

- `repvit_m1_15plus5_v1.pt`: PyTorch checkpoint.
- `repvit_m1_15plus5_v1.manifest.json`: SKU ID/name map and training provenance.

## Requirements

Python 3.11 and `torch`, `torchvision`, `timm`, and `Pillow` are required.
This package was verified with Torch 2.13.0, Torchvision 0.28.0, and timm
1.0.28.

## Minimal inference

```python
import json
import timm
import torch
from PIL import Image
from torchvision import transforms

checkpoint = torch.load("repvit_m1_15plus5_v1.pt", map_location="cpu", weights_only=True)
manifest = json.load(open("repvit_m1_15plus5_v1.manifest.json", encoding="utf-8"))
model = timm.create_model("repvit_m1", pretrained=False, num_classes=20)
model.load_state_dict(checkpoint["state_dict"], strict=True)
model.eval()

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])
with Image.open("product_crop.jpg") as image, torch.inference_mode():
    probabilities = torch.softmax(model(transform(image.convert("RGB")).unsqueeze(0)), dim=1)[0]
    values, indices = probabilities.topk(3)
    sku_ids = [sku_id for sku_id, _ in sorted(checkpoint["class_index"].items(), key=lambda item: item[1])]
    names = {item["id"]: item["name"] for item in manifest["class_map"]}
    print([(sku_ids[index], names[sku_ids[index]], float(value)) for value, index in zip(values, indices)])
```

For desktop-equivalent inference from a detector box, make three RGB crops
with 5%, 10%, and 15% padding, apply the same transform to each crop, then
average their softmax probability vectors before choosing the Top-3.
