"""
PIPELINE STEP 3 — Prompt Generator
Converts content ideas → precise SD/FLUX image prompts + video prompts
Ensures Aanya's visual identity is baked into every generation
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.rate_limiter import get_limiter
from utils.storage import save_json, load_json
from pipeline._llm_utils import llm  # shared LLM caller

log = get_logger("prompt_generator")
limiter = get_limiter()

CHARACTER_CONFIG = load_json(os.getenv("CHARACTER_CONFIG", "./character/character_config.json"))


# ─── Character Identity Lock ────────────────────────────────────────────────
BASE_POSITIVE = CHARACTER_CONFIG.get("image_generation", {}).get(
    "base_positive_prompt",
    "beautiful indian girl, photorealistic, 8k, warm wheatish complexion, large expressive brown eyes, long dark hair, charming smile, national crush"
)

BASE_NEGATIVE = CHARACTER_CONFIG.get("image_generation", {}).get(
    "negative_prompt",
    "ugly, deformed, blurry, low quality, western features, cartoon, anime, nsfw, extra limbs"
)

STYLE_MODIFIERS = CHARACTER_CONFIG.get("image_generation", {}).get("style_modifiers", {})

LORA_TRIGGER = CHARACTER_CONFIG.get("image_generation", {}).get(
    "lora_config", {}
).get("trigger_word", "aanya_sharma_v1")

# Platform-specific image dimensions
PLATFORM_DIMS = {
    "instagram_feed":     {"width": 1080, "height": 1350, "ratio": "4:5 portrait"},
    "instagram_reel":     {"width": 1080, "height": 1920, "ratio": "9:16 vertical"},
    "instagram_story":    {"width": 1080, "height": 1920, "ratio": "9:16 vertical"},
    "instagram_carousel": {"width": 1080, "height": 1080, "ratio": "1:1 square"},
    "youtube_short":      {"width": 1080, "height": 1920, "ratio": "9:16 vertical"},
    "youtube_thumbnail":  {"width": 1280, "height": 720,  "ratio": "16:9 landscape"},
}


# ─── Mood → Style Mapping ────────────────────────────────────────────────────
PILLAR_STYLE_MAP = {
    "morning_mindset":       "morning_motivation",
    "mindset_shifts":        "mindset_power",
    "indian_girl_struggles": "relatable_candid",
    "success_hustle":        "mindset_power",
    "self_love_glow":        "self_love_glow",
    "festival_culture":      "festive_ethnic"
}

MOOD_LIGHTING = {
    "morning_motivation": "golden hour sunrise, warm amber rays, soft lens flare",
    "mindset_power":      "dramatic side lighting, confident directional light, deep shadows",
    "relatable_candid":   "soft indoor warm light, fairy lights bokeh, cozy atmosphere",
    "festive_ethnic":     "festive warm glow, diya light, golden bokeh, celebration",
    "self_love_glow":     "soft diffused natural light, ethereal glow, pastel tones"
}


# ─── Image Prompt Builder ────────────────────────────────────────────────────
def build_image_prompt(idea: Dict) -> Dict:
    """Build complete positive + negative prompt for an image"""
    pillar = idea.get("pillar", "morning_mindset")
    visual_concept = idea.get("visual_concept", "")
    platform = idea.get("platform", "instagram_feed")

    # Map pillar → style modifier key
    style_key = PILLAR_STYLE_MAP.get(pillar, "morning_motivation")
    style_mod = STYLE_MODIFIERS.get(style_key, "")
    lighting = MOOD_LIGHTING.get(style_key, "natural soft lighting")

    dims = PLATFORM_DIMS.get(platform, PLATFORM_DIMS["instagram_feed"])

    # Compose positive prompt
    positive = (
        f"{LORA_TRIGGER}, "  # LoRA trigger first for weight
        f"{BASE_POSITIVE}, "
        f"{style_mod}, "
        f"{lighting}, "
        f"{visual_concept}, "
        f"social media content, instagram worthy, viral aesthetic, "
        f"{dims['ratio']} composition"
    ).replace(", ,", ",").strip(", ")

    return {
        "positive": positive,
        "negative": BASE_NEGATIVE,
        "width": dims["width"],
        "height": dims["height"],
        "platform": platform,
        "style_key": style_key
    }


# ─── LLM-Enhanced Prompt Refinement ─────────────────────────────────────────
def refine_prompt_with_llm(idea: Dict, base_prompt: Dict) -> Dict:
    """Use LLM to enhance prompt specificity for maximum visual quality"""

    prompt = f"""You are an expert Stable Diffusion / FLUX prompt engineer specializing in photorealistic Indian portrait photography for social media.

CONTENT IDEA:
Title: {idea.get('title', '')}
Platform: {idea.get('platform', '')}
Visual Concept: {idea.get('visual_concept', '')}
Pillar/Mood: {idea.get('pillar', '')}

CURRENT BASE PROMPT:
{base_prompt['positive']}

CHARACTER (MUST PRESERVE):
- Beautiful Indian girl, national crush, warm wheatish complexion
- Large expressive brown eyes with kajal, long dark hair
- Charming smile, graceful, indo-western fashion

Task: Refine and enhance the positive prompt to make it more specific, cinematic, and likely to generate a viral-quality image.
Add: specific clothing details, exact pose, background elements, lighting quality, camera angle.
Keep: all character identity tokens, LORA trigger word "{LORA_TRIGGER}".
Limit: 150 words maximum.

Return ONLY the refined positive prompt text. No explanation."""

    refined = llm(prompt)
    if refined and len(refined) > 50:
        base_prompt["positive"] = refined.strip()
        log.debug("Prompt refined by LLM")

    return base_prompt


# ─── Video Prompt Builder ────────────────────────────────────────────────────
def build_video_prompt(idea: Dict) -> Dict:
    """Build AnimateDiff/video generation prompt"""
    pillar = idea.get("pillar", "morning_mindset")
    visual_concept = idea.get("visual_concept", "")
    style_key = PILLAR_STYLE_MAP.get(pillar, "morning_motivation")
    style_mod = STYLE_MODIFIERS.get(style_key, "")

    motion_types = {
        "morning_motivation": "slow gentle head turn, hair moves slightly, warm smile forms",
        "mindset_power":      "confident slow walk toward camera, direct eye contact",
        "relatable_candid":   "laughing candidly, natural movement, spontaneous",
        "festive_ethnic":     "graceful slow twirl, dupatta flows, festive joy",
        "self_love_glow":     "gentle looking up at sky, peaceful sigh, eyes close and open"
    }

    motion = motion_types.get(style_key, "slow natural movement, breathing, blinking")

    positive = (
        f"{LORA_TRIGGER}, {BASE_POSITIVE}, {style_mod}, "
        f"{visual_concept}, {motion}, "
        f"smooth cinematic motion, 24fps, no camera shake, "
        f"instagram reel quality, viral short video"
    )

    return {
        "positive": positive,
        "negative": BASE_NEGATIVE + ", static, frozen, jerky motion, low fps",
        "width": 576,
        "height": 1024,
        "frames": 32,
        "fps": 8,
        "motion_scale": 1.2,
        "platform": "instagram_reel"
    }


# ─── Carousel Prompt Builder ─────────────────────────────────────────────────
def build_carousel_prompts(idea: Dict, slides: int = 5) -> List[Dict]:
    """Build prompts for carousel slides (consistent character, varied backgrounds)"""
    log.info(f"Building {slides}-slide carousel prompts...")

    pillar = idea.get("pillar", "morning_mindset")
    style_key = PILLAR_STYLE_MAP.get(pillar, "morning_motivation")

    slide_contexts = [
        f"slide 1 hook, impactful expression, bold pose",
        f"slide 2 story, thoughtful expression, hands gesturing",
        f"slide 3 insight, looking into distance, peaceful",
        f"slide 4 relatable moment, slight smile, candid",
        f"slide 5 conclusion, direct eye contact, confident smile"
    ]

    prompts = []
    for i, context in enumerate(slide_contexts[:slides]):
        style_mod = STYLE_MODIFIERS.get(style_key, "")
        positive = (
            f"{LORA_TRIGGER}, {BASE_POSITIVE}, {style_mod}, "
            f"{context}, 1:1 square composition, instagram carousel, "
            f"consistent character across slides"
        )
        prompts.append({
            "slide": i + 1,
            "positive": positive,
            "negative": BASE_NEGATIVE,
            "width": 1080,
            "height": 1080
        })

    return prompts


# ─── Main ────────────────────────────────────────────────────────────────────
def generate_prompts(ideas_data: Dict) -> Dict:
    """Generate all prompts for selected content ideas"""
    log.info("=" * 50)
    log.info("STEP 3: Prompt Generator Starting")
    log.info("=" * 50)

    selected_ideas = ideas_data.get("selected_ideas", [])
    if not selected_ideas:
        log.error("No ideas to generate prompts for")
        return {}

    prompt_packages = []

    for idea in selected_ideas:
        log.info(f"Building prompts for: {idea.get('title', 'Unknown')}")
        platform = idea.get("platform", "instagram_feed")

        package = {
            "idea": idea,
            "platform": platform,
            "content_type": "image"
        }

        if "reel" in platform or "short" in platform:
            # Primary: video prompt + thumbnail image
            package["content_type"] = "video"
            package["video_prompt"] = build_video_prompt(idea)
            # Thumbnail for the reel
            img_prompt = build_image_prompt({**idea, "platform": "instagram_feed"})
            package["thumbnail_prompt"] = refine_prompt_with_llm(idea, img_prompt)

        elif "carousel" in platform:
            package["content_type"] = "carousel"
            package["carousel_prompts"] = build_carousel_prompts(idea, slides=5)

        else:
            # Standard image post
            img_prompt = build_image_prompt(idea)
            package["image_prompt"] = refine_prompt_with_llm(idea, img_prompt)

        prompt_packages.append(package)
        log.success(f"Prompts ready: {idea.get('title', 'Unknown')[:50]}")

    result = {
        "generated_at": datetime.now().isoformat(),
        "prompt_packages": prompt_packages,
        "total": len(prompt_packages)
    }

    save_json(result, f"prompts_{datetime.now().strftime('%Y%m%d')}.json", "data/content_queue")
    log.success(f"Prompt generation complete. {len(prompt_packages)} packages ready.")
    return result


if __name__ == "__main__":
    dummy_ideas = {
        "selected_ideas": [
            {
                "title": "Log kya kahenge — stop caring now",
                "pillar": "indian_girl_struggles",
                "platform": "instagram_reel",
                "visual_concept": "Aanya confident pose, morning terrace, direct eye contact",
                "hook": "Kitni baar tune apna sapna choda? 👀",
                "core_message": "Stop living for others' opinions"
            }
        ]
    }
    result = generate_prompts(dummy_ideas)
    print(json.dumps(result, indent=2, ensure_ascii=False))
