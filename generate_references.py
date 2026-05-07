"""
Generate 30 reference images of Aanya Sharma for LoRA training
Uses Pollinations.ai — completely free
python generate_references.py
"""
import time, urllib.parse, sys
from pathlib import Path

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

OUT = Path("character/reference_images")
OUT.mkdir(parents=True, exist_ok=True)

BASE = (
    "beautiful indian girl, national crush, 22 years old, "
    "warm wheatish golden skin, large expressive kajal-lined brown eyes, "
    "long dark silky hair, full lips, sharp elegant facial features, "
    "charming warm smile, photorealistic 8k, hyperdetailed skin, "
    "canon 85mm portrait lens, bokeh background"
)

VARIATIONS = [
    ("morning terrace golden hour, white kurta, warm amber light, chai cup", 1080, 1350),
    ("direct eye contact close-up, confident smirk, maroon ethnic top, minimal background", 1080, 1350),
    ("candid laugh, indo-western kurta jeans, outdoor park, natural light", 1080, 1350),
    ("reading book in cafe, sunlight, thoughtful expression, casual ethnic top", 1080, 1080),
    ("rooftop golden hour, dupatta in breeze, pink kurta, city background", 1080, 1350),
    ("festive saree deep burgundy, gold jewelry, bindi, diya background", 1080, 1350),
    ("cozy home, oversized hoodie, fairy lights, late evening warm light", 1080, 1920),
    ("college campus, kurta jeans dupatta, books, sunny day, candid", 1080, 1350),
    ("fitness park, athletic indo-western, morning jog, fresh face", 1080, 1350),
    ("half face close up, kajal eyes, sharp features, dark background dramatic", 1080, 1350),
]

print("\n🌸 Generating Aanya's Reference Images for LoRA Training")
print(f"   Saving to: {OUT.resolve()}\n")

count = 0
for seed_base in range(3):          # 3 rounds × 10 variations = 30 images
    for i, (scene, w, h) in enumerate(VARIATIONS):
        seed = seed_base * 100 + i + 1
        filename = f"aanya_ref_{count+1:03d}_seed{seed}.jpg"
        filepath = OUT / filename

        if filepath.exists():
            print(f"  ⏭  Skip (exists): {filename}")
            count += 1
            continue

        prompt = f"{BASE}, {scene}"
        encoded = urllib.parse.quote(prompt[:450])
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width={w}&height={h}&model=flux&nologo=true&seed={seed}")

        print(f"  [{count+1:02d}/30] {scene[:50]}...", end=" ", flush=True)
        try:
            r = requests.get(url, timeout=90)
            if r.ok and len(r.content) > 8000:
                filepath.write_bytes(r.content)
                print(f"✅ ({len(r.content)//1024}KB)")
            else:
                print(f"✗ {r.status_code}")
        except Exception as e:
            print(f"✗ {e}")

        count += 1
        time.sleep(4)   # Pollinations rate limit

print(f"\n✅ Done! {len(list(OUT.glob('*.jpg')))} reference images saved.")
print(f"   Path: {OUT.resolve()}")
print(f"\nNext: Follow lora_training_guide.md to train Aanya's LoRA model.")
