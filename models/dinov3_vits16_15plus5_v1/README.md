# DINOv3 ViT-S/16 15+5 v1

20-SKU bakery product classifier. This uses DINOv3 ViT-S/16 embeddings and
support built from an existing 15-SKU set with five additional SKUs (4, 6, 9,
15, and 16).

## Files

- `dinov3_vits16_pretrain_lvd1689m-08c60483.pth`: DINOv3 ViT-S/16 weights.
- `dinov3_vits16_15plus5_v1_support.pt`: SKU ID/name map and 20 SKU prototypes.

## Requirements

Python 3.11 and `torch`, `torchvision`, `Pillow`, and the DINOv3 Python
package are required. This package was verified with Torch 2.13.0 and
Torchvision 0.28.0. The DINOv3 package must provide
`dinov3.models.vision_transformer.vit_small`.

## Minimal inference

```python
import torch
import torch.nn.functional as functional
from PIL import Image
from torchvision import transforms
from dinov3.models.vision_transformer import vit_small

weights = torch.load("dinov3_vits16_pretrain_lvd1689m-08c60483.pth", map_location="cpu", weights_only=True)
support = torch.load("dinov3_vits16_15plus5_v1_support.pt", map_location="cpu", weights_only=True)
model = vit_small(patch_size=16, n_storage_tokens=4, mask_k_bias=True, layerscale_init=1e-5)
model.load_state_dict(weights, strict=True)
model.eval()

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])
with Image.open("product_crop.jpg") as image, torch.inference_mode():
    embedding = functional.normalize(model(transform(image.convert("RGB")).unsqueeze(0)), dim=1)[0]
    values, indices = (support["prototypes"] @ embedding).topk(3)
    print([(support["class_map"][index]["id"], support["class_map"][index]["name"], float(value)) for value, index in zip(values, indices)])
```

For desktop-equivalent inference from a detector box, make three RGB crops
with 5%, 10%, and 15% padding, apply the same transform to each crop, then
average their L2-normalized embeddings before choosing the Top-3.
