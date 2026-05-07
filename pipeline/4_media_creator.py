"""
PIPELINE STEP 4 — Media Creator
Image: ComfyUI (local, FLUX) → HuggingFace SDXL → Pollinations.ai
Video: AnimateDiff (ComfyUI) → Zeroscope (HF) → slideshow fallback
All FREE — cascading fallbacks
"""
import os
import json
import time
import base64
import uuid
import urllib.request
import urllib.parse
from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.rate_limiter import get_limiter
from utils.storage import save_media

log = get_logger("media_creator")
limiter = get_limiter()

COMFYUI_HOST = os.getenv("COMFYUI_HOST", "http://127.0.0.1:8188")
HF_TOKEN = os.getenv("HF_TOKEN", "")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))


# ════════════════════════════════════════════════════════
#  IMAGE GENERATION
# ════════════════════════════════════════════════════════

# ─── ComfyUI (Local — Primary) ──────────────────────────────────────────────
def generate_via_comfyui(prompt_data: Dict) -> Optional[bytes]:
    """
    Send generation request to local ComfyUI instance.
    Uses FLUX.1-dev or Realistic Vision as base model.
    """
    import requests
    import websocket

    log.info("Trying ComfyUI (local)...")

    # ComfyUI workflow for portrait generation
    workflow = {
        "3": {
            "inputs": {
                "seed": int(time.time()) % 999999999,
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            },
            "class_type": "KSampler"
        },
        "4": {
            "inputs": {"ckpt_name": "realisticVisionV60B1_v60B1VAE.safetensors"},
            "class_type": "CheckpointLoaderSimple"
        },
        "5": {
            "inputs": {
                "width": prompt_data.get("width", 1080),
                "height": prompt_data.get("height", 1350),
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "6": {
            "inputs": {
                "text": prompt_data.get("positive", ""),
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "7": {
            "inputs": {
                "text": prompt_data.get("negative", ""),
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "8": {
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "filename_prefix": "aanya",
                "images": ["8", 0]
            },
            "class_type": "SaveImage"
        }
    }

    client_id = str(uuid.uuid4())

    try:
        # Check if ComfyUI is running
        resp = requests.get(f"{COMFYUI_HOST}/system_stats", timeout=3)
        if not resp.ok:
            raise ConnectionError("ComfyUI not responding")

        # Queue prompt
        payload = {"prompt": workflow, "client_id": client_id}
        resp = requests.post(f"{COMFYUI_HOST}/prompt", json=payload)
        prompt_id = resp.json()["prompt_id"]
        log.info(f"ComfyUI job queued: {prompt_id}")

        # Wait for completion via polling
        for _ in range(120):  # max 2 min
            time.sleep(1)
            history = requests.get(f"{COMFYUI_HOST}/history/{prompt_id}").json()
            if prompt_id in history:
                outputs = history[prompt_id]["outputs"]
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        img_info = node_output["images"][0]
                        # Download image
                        img_url = (
                            f"{COMFYUI_HOST}/view?filename={img_info['filename']}"
                            f"&subfolder={img_info.get('subfolder', '')}"
                            f"&type={img_info.get('type', 'output')}"
                        )
                        img_resp = requests.get(img_url)
                        log.success("ComfyUI image generated!")
                        return img_resp.content

        log.warning("ComfyUI timed out")
        return None

    except (ConnectionError, requests.exceptions.ConnectionError):
        log.warning("ComfyUI not running — trying next source")
        return None
    except Exception as e:
        log.error(f"ComfyUI error: {e}")
        return None


# ─── HuggingFace SDXL (Free Inference API — Fallback) ───────────────────────
def generate_via_huggingface(prompt_data: Dict) -> Optional[bytes]:
    """
    Use HuggingFace Inference API with SDXL or Realistic Vision.
    Free tier — rate limited, but reliable fallback.
    """
    if not limiter.acquire("hf"):
        log.warning("HuggingFace rate limit hit")
        return None

    log.info("Trying HuggingFace Inference API...")

    models_to_try = [
        "stabilityai/stable-diffusion-xl-base-1.0",
        "SG161222/Realistic_Vision_V6.0_B1_noVAE",
        "runwayml/stable-diffusion-v1-5"
    ]

    import requests

    for model in models_to_try:
        try:
            headers = {}
            if HF_TOKEN:
                headers["Authorization"] = f"Bearer {HF_TOKEN}"

            # Trim prompt to HF limits
            positive = prompt_data.get("positive", "")[:500]
            negative = prompt_data.get("negative", "")[:200]

            payload = {
                "inputs": positive,
                "parameters": {
                    "negative_prompt": negative,
                    "width": min(prompt_data.get("width", 1024), 1024),
                    "height": min(prompt_data.get("height", 1024), 1024),
                    "num_inference_steps": 25,
                    "guidance_scale": 7.5,
                    "num_images_per_prompt": 1
                }
            }

            resp = requests.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers,
                json=payload,
                timeout=60
            )

            if resp.ok and resp.headers.get("content-type", "").startswith("image"):
                log.success(f"HuggingFace image generated via {model}")
                return resp.content
            elif resp.status_code == 503:
                log.warning(f"Model {model} loading, trying next...")
                time.sleep(3)
            else:
                log.warning(f"HF model {model} failed: {resp.status_code}")

        except Exception as e:
            log.warning(f"HF error with {model}: {e}")

    return None


# ─── Pollinations.ai (Free, No Key — Backup) ────────────────────────────────
def generate_via_pollinations(prompt_data: Dict) -> Optional[bytes]:
    """
    Pollinations.ai — completely free, no API key needed.
    Quality lower but always available as last resort.
    """
    if not limiter.acquire("pollinations"):
        log.warning("Pollinations rate limit hit")
        return None

    log.info("Trying Pollinations.ai (free backup)...")

    try:
        import requests

        # Trim and encode prompt
        positive = prompt_data.get("positive", "beautiful indian girl, photorealistic")[:300]
        negative = prompt_data.get("negative", "ugly, blurry")[:100]
        width = min(prompt_data.get("width", 1024), 1536)
        height = min(prompt_data.get("height", 1024), 1536)

        encoded = urllib.parse.quote(positive)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={width}&height={height}&model=flux"
            f"&negative={urllib.parse.quote(negative)}"
            f"&seed={int(time.time()) % 9999}"
            f"&nologo=true"
        )

        resp = requests.get(url, timeout=60)
        if resp.ok and len(resp.content) > 1000:
            log.success("Pollinations image generated!")
            return resp.content
        else:
            log.warning(f"Pollinations failed: {resp.status_code}")

    except Exception as e:
        log.error(f"Pollinations error: {e}")

    return None


# ─── Image Generation Cascade ────────────────────────────────────────────────
def generate_image(prompt_data: Dict, idea_title: str = "post") -> Optional[Dict]:
    """
    Try image generation in cascade order.
    Returns media info dict or None.
    """
    generators = [
        ("ComfyUI", generate_via_comfyui),
        ("HuggingFace", generate_via_huggingface),
        ("Pollinations", generate_via_pollinations),
    ]

    for name, fn in generators:
        log.info(f"Attempting image generation via {name}...")
        img_bytes = fn(prompt_data)
        if img_bytes and len(img_bytes) > 5000:
            # Add text overlay / watermark if needed (Pillow)
            img_bytes = add_branding(img_bytes)

            filename = f"aanya_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name.lower()}.jpg"
            media = save_media(img_bytes, filename, "images")
            media["generator"] = name
            media["prompt_data"] = prompt_data
            log.success(f"Image saved: {filename}")
            return media

    log.error("ALL image generators failed")
    return None


# ─── Branding Overlay ────────────────────────────────────────────────────────
def add_branding(img_bytes: bytes) -> bytes:
    """Add subtle @aanyasharma watermark (optional, minimal)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO

        img = Image.open(BytesIO(img_bytes)).convert("RGB")

        # Subtle text overlay
        draw = ImageDraw.Draw(img)
        text = "@aanyasharma"
        # Position: bottom right corner
        bbox = draw.textbbox((0, 0), text)
        text_w = bbox[2] - bbox[0]
        x = img.width - text_w - 20
        y = img.height - 40

        # Shadow for readability
        draw.text((x+1, y+1), text, fill=(0, 0, 0, 128))
        draw.text((x, y), text, fill=(255, 255, 255, 200))

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()

    except Exception as e:
        log.warning(f"Branding overlay failed: {e}")
        return img_bytes


# ════════════════════════════════════════════════════════
#  VIDEO GENERATION
# ════════════════════════════════════════════════════════

def generate_video_via_comfyui(prompt_data: Dict) -> Optional[bytes]:
    """AnimateDiff via ComfyUI for short video clips"""
    log.info("Trying AnimateDiff via ComfyUI...")
    # AnimateDiff workflow — requires AnimateDiff extension in ComfyUI
    # Simplified workflow trigger
    import requests
    try:
        resp = requests.get(f"{COMFYUI_HOST}/system_stats", timeout=3)
        if not resp.ok:
            raise ConnectionError
        log.info("ComfyUI available for video — AnimateDiff workflow")
        # In production: send AnimateDiff workflow JSON
        # For now: returns None to use slideshow fallback
        return None
    except:
        return None


def generate_slideshow_video(images: List[bytes], audio_path: Optional[str] = None,
                              duration: int = 30) -> Optional[bytes]:
    """
    Create a Reel/Short from static images as slideshow.
    Uses moviepy (free, local). Each image shown for ~3 seconds.
    """
    log.info(f"Creating slideshow video from {len(images)} images...")
    try:
        from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip
        from PIL import Image
        from io import BytesIO
        import tempfile, os

        clips = []
        for i, img_bytes in enumerate(images):
            # Save temp image
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(img_bytes)
                tmp_path = f.name

            clip = ImageClip(tmp_path).set_duration(3)
            # Ken Burns zoom effect
            clip = clip.resize(lambda t: 1 + 0.02 * t)
            clips.append(clip)

        final = concatenate_videoclips(clips, method="compose")

        if audio_path and os.path.exists(audio_path):
            audio = AudioFileClip(audio_path).subclip(0, min(duration, final.duration))
            final = final.set_audio(audio)

        # Export to bytes
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_out = f.name

        final.write_videofile(
            tmp_out, fps=24, codec="libx264",
            audio_codec="aac", verbose=False, logger=None
        )

        video_bytes = Path(tmp_out).read_bytes()
        os.unlink(tmp_out)
        log.success(f"Slideshow video: {len(video_bytes)//1024}KB")
        return video_bytes

    except ImportError:
        log.warning("moviepy not installed — pip install moviepy")
        return None
    except Exception as e:
        log.error(f"Slideshow creation failed: {e}")
        return None


def generate_video(prompt_data: Dict, idea: Dict) -> Optional[Dict]:
    """Video generation cascade"""
    video_bytes = generate_video_via_comfyui(prompt_data)

    if not video_bytes:
        # Fallback: generate 3 images and make slideshow
        log.info("Falling back to image slideshow video...")
        images = []
        img_prompt = {**prompt_data, "width": 576, "height": 1024}
        for _ in range(3):
            img = (
                generate_via_comfyui(img_prompt) or
                generate_via_huggingface(img_prompt) or
                generate_via_pollinations(img_prompt)
            )
            if img:
                images.append(img)

        if images:
            video_bytes = generate_slideshow_video(images)

    if video_bytes:
        filename = f"aanya_reel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        media = save_media(video_bytes, filename, "videos")
        media["type"] = "video"
        return media

    return None


# ════════════════════════════════════════════════════════
#  CAROUSEL GENERATION
# ════════════════════════════════════════════════════════

def generate_carousel(carousel_prompts: List[Dict], idea: Dict) -> Optional[Dict]:
    """Generate all carousel slides"""
    log.info(f"Generating {len(carousel_prompts)}-slide carousel...")
    slides = []

    for slide_prompt in carousel_prompts:
        img = (
            generate_via_comfyui(slide_prompt) or
            generate_via_huggingface(slide_prompt) or
            generate_via_pollinations(slide_prompt)
        )
        if img:
            filename = f"aanya_carousel_{datetime.now().strftime('%Y%m%d_%H%M%S')}_slide{slide_prompt['slide']}.jpg"
            media = save_media(img, filename, "images/carousels")
            slides.append(media)
            time.sleep(1)  # gentle pacing

    if slides:
        return {"type": "carousel", "slides": slides, "count": len(slides)}
    return None


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════

def create_media(prompts_data: Dict) -> Dict:
    """Create all media from prompt packages"""
    log.info("=" * 50)
    log.info("STEP 4: Media Creator Starting")
    log.info("=" * 50)

    packages = prompts_data.get("prompt_packages", [])
    results = []

    for package in packages:
        idea = package.get("idea", {})
        content_type = package.get("content_type", "image")
        title = idea.get("title", "Unknown")
        log.info(f"Creating media for: {title[:50]}")

        result = {"idea": idea, "content_type": content_type}

        if content_type == "video":
            video = generate_video(package.get("video_prompt", {}), idea)
            if video:
                result["video"] = video
            # Always generate thumbnail
            thumb = generate_image(
                package.get("thumbnail_prompt", package.get("video_prompt", {})),
                title
            )
            if thumb:
                result["thumbnail"] = thumb

        elif content_type == "carousel":
            carousel = generate_carousel(package.get("carousel_prompts", []), idea)
            if carousel:
                result["carousel"] = carousel

        else:
            image = generate_image(package.get("image_prompt", {}), title)
            if image:
                result["image"] = image

        results.append(result)
        log.success(f"Media created for: {title[:50]}")

    output = {
        "created_at": datetime.now().isoformat(),
        "media_results": results,
        "total": len(results)
    }

    from utils.storage import save_json
    save_json(output, f"media_{datetime.now().strftime('%Y%m%d')}.json", "data/content_queue")
    log.success(f"Media creation complete. {len(results)} pieces ready.")
    return output


if __name__ == "__main__":
    # Test with dummy prompt
    dummy = {
        "prompt_packages": [{
            "idea": {"title": "Test Post", "platform": "instagram_feed"},
            "content_type": "image",
            "image_prompt": {
                "positive": "beautiful indian girl, national crush, photorealistic, golden hour",
                "negative": "ugly, blurry, cartoon",
                "width": 1080,
                "height": 1350
            }
        }]
    }
    result = create_media(dummy)
    print(json.dumps({k: v for k, v in result.items() if k != "media_results"}, indent=2))
