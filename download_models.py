"""
Download free AI models for Aanya image generation
Run: python download_models.py
"""
import os, sys, urllib.request
from pathlib import Path

PYTHON = sys.executable

def download(url, dest, name):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  ✅ Already exists: {name}")
        return
    print(f"  ⬇  Downloading {name} ({url.split('/')[-1]})...")
    try:
        urllib.request.urlretrieve(url, dest, lambda b,bs,ts: print(f"\r  {b*bs/ts*100:.0f}%", end=""))
        print(f"\n  ✅ Saved: {dest}")
    except Exception as e:
        print(f"\n  ✗  Failed: {e}")

COMFYUI_DIR = Path("C:/Users/admin/ComfyUI")

# HuggingFace direct download links (free)
MODELS = [
    {
        "name": "Realistic Vision V6 (Best for Indian portraits)",
        "url": "https://huggingface.co/SG161222/Realistic_Vision_V6.0_B1_noVAE/resolve/main/Realistic_Vision_V6.0_B1_fp16.safetensors",
        "dest": COMFYUI_DIR / "models/checkpoints/realisticVisionV60.safetensors"
    },
    {
        "name": "VAE (for Realistic Vision)",
        "url": "https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors",
        "dest": COMFYUI_DIR / "models/vae/vae-ft-mse.safetensors"
    }
]

if __name__ == "__main__":
    print("\n=== Downloading AI Models for Aanya ===\n")
    if not COMFYUI_DIR.exists():
        print("⚠  ComfyUI not found. Run install_comfyui.bat first.")
        print("   Saving to local models/ instead...")
        for m in MODELS:
            m["dest"] = Path("models") / Path(m["dest"]).name

    for m in MODELS:
        print(f"\n{m['name']}")
        download(m["url"], m["dest"], m["name"])

    print("\n✅ Done! Models ready for ComfyUI.")
