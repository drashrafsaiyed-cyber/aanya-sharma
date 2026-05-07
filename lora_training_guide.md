# Aanya Sharma — LoRA Training Guide

## What is LoRA?
A small AI model (4-50MB) trained on Aanya's reference images.
Once trained, every image generated will have the SAME face — consistent identity.

## Step 1: Generate Reference Images (do this first)
Run: `python generate_references.py`
This creates 30 reference images of Aanya via Pollinations.
Save them to: `character/reference_images/`

## Step 2: Install Kohya_ss (free LoRA trainer)
```bash
cd C:\Users\admin
git clone https://github.com/bmaltais/kohya_ss.git
cd kohya_ss
python -m pip install -r requirements.txt
```

## Step 3: Prepare Training Data
- Put 30 reference images in: `character/reference_images/`
- Create caption file for each: `image001.txt` containing:
  `aanya_sharma_v1, beautiful indian girl, national crush`

## Step 4: Train
In kohya_ss GUI:
- Base model: realisticVisionV60.safetensors
- Training images: character/reference_images/
- Output: character/lora_weights/aanya_v1.safetensors
- Steps: 1500-2000
- Trigger word: aanya_sharma_v1

## Step 5: Use in ComfyUI
Load LoRA node → select aanya_v1.safetensors → weight: 0.8
Every image will now have Aanya's consistent face.

## Alternative: Use IP-Adapter (no training needed)
In ComfyUI, use IP-Adapter with one reference image.
Weight: 0.8 — gives 70% face consistency without training.
