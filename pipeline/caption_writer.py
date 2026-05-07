"""
PIPELINE STEP 5 — Caption Writer
Writes Hinglish captions + hashtags for every platform & content type
Aanya's voice: warm, bold, relatable, Indian-girl energy
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.storage import save_json, load_json
from pipeline._llm_utils import llm, parse_json_response

log = get_logger("caption_writer")

CHARACTER_CONFIG = load_json(os.getenv("CHARACTER_CONFIG", "./character/character_config.json"))
HASHTAG_STRATEGY = CHARACTER_CONFIG.get("hashtag_strategy", {})


# ─── Aanya's Caption Voice Prompt ────────────────────────────────────────────
CAPTION_SYSTEM = """You are writing captions AS Aanya Sharma — a 22-year-old Indian girl influencer.

AANYA'S VOICE (NON-NEGOTIABLE):
- Language: Hinglish — gender-neutral "yaar/tu/tujhe" so BOTH boys AND girls feel addressed
- Tone: Dream girlfriend energy for boys. Ride-or-die bestie energy for girls. Same words, both feel it.
  She confides. She hypes. She teases. She never lectures. She makes you feel SEEN.
- Style: Starts mid-conversation. Like a voice note she sent just to YOU.
- Energy: "Yaar sun—" / "Ek baat poochu?" / "Tujhse honestly baat karni thi" / "Bata mujhe"
- Emojis: Natural, how she'd actually type — 👀✨💕😭🔥👑🌸💫
- NEVER: "girls listen", "ladies", "beta" — always gender-neutral so everyone feels included

CAPTION STRUCTURE (always follow):
1. HOOK (line 1): Like a bestie opening a conversation — question, confession, or bold claim. Hinglish.
   Examples: "Yaar, kisi ne bola tha tumhe bhi? 👀" / "Okay sun, yeh important hai." / "Tujhse kuch honestly baat karni thi."
2. THE REAL PART (2-4 lines): She shares, she doesn't lecture. Personal, specific, Indian.
   She acknowledges the struggle first — then the hype.
3. THE LINE THEY'LL SCREENSHOT (1 line): Punchy, quotable, all hers.
4. CTA (1 line): Like a bestie asking — "tag kar yaar", "bata mujhe", "comment kar ❤️"
5. LINE BREAK then HASHTAGS

FORBIDDEN:
- Big sister / mentor / teacher tone (zero lectures)
- Full English paragraphs
- Corporate motivation ("hustle hard", "rise and grind", "you got this!")
- Toxic positivity without first acknowledging the real struggle
- Political opinions, body shaming"""


# ─── Platform-Specific Caption Rules ─────────────────────────────────────────
PLATFORM_RULES = {
    "instagram_feed": {
        "max_length": 2200,
        "ideal_length": 150,
        "hashtags": 25,
        "note": "First 125 chars visible before 'more' — hook must be there"
    },
    "instagram_reel": {
        "max_length": 2200,
        "ideal_length": 80,
        "hashtags": 20,
        "note": "Short punchy — reel speaks for itself. Caption is support."
    },
    "instagram_carousel": {
        "max_length": 2200,
        "ideal_length": 200,
        "hashtags": 25,
        "note": "Tease the slides. '5 cheezon ko aaj hi badle' energy"
    },
    "instagram_story": {
        "max_length": 500,
        "ideal_length": 50,
        "hashtags": 5,
        "note": "Ultra short. Text overlay on visual does the work."
    },
    "youtube_short": {
        "max_length": 5000,
        "ideal_length": 200,
        "hashtags": 15,
        "note": "Description matters for YouTube SEO. Add Hindi keywords."
    }
}


# ─── Hashtag Builder ──────────────────────────────────────────────────────────
def build_hashtags(idea: Dict, platform: str) -> str:
    """Build platform-appropriate hashtag set"""
    pillar = idea.get("pillar", "morning_mindset")
    hashtag_themes = idea.get("hashtag_themes", [])
    platform_key = platform.replace("instagram_", "").replace("youtube_", "")

    rules = PLATFORM_RULES.get(platform, {})
    max_tags = rules.get("hashtags", 20)

    # Fixed branded tags (always include)
    branded = HASHTAG_STRATEGY.get("tier_3_branded", ["#AanyaSharma"])

    # Tier 1 — broad reach
    tier1 = HASHTAG_STRATEGY.get("tier_1_reach", [])[:5]

    # Tier 2 — niche
    tier2 = HASHTAG_STRATEGY.get("tier_2_niche", [])[:8]

    # Content-specific from idea
    content_tags = [f"#{t.replace(' ', '').replace('#', '')}" for t in hashtag_themes]

    # Pillar-specific tags
    pillar_tags = {
        "morning_mindset":       ["#MorningMotivation", "#SubahKiShuruat", "#GoodMorningIndia"],
        "mindset_shifts":        ["#MindsetMatters", "#SochoBado", "#GrowthMindset"],
        "indian_girl_struggles": ["#IndianGirl", "#LogKyaKahenge", "#GirlPower"],
        "success_hustle":        ["#SuccessMindset", "#StudyMotivation", "#CareerGoals"],
        "self_love_glow":        ["#SelfLove", "#KhudSeKaro", "#ConfidenceBoost"],
        "festival_culture":      ["#IndianCulture", "#Festival", "#DesiVibes"]
    }.get(pillar, [])

    all_tags = branded + content_tags + pillar_tags + tier2 + tier1
    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for tag in all_tags:
        tag = tag if tag.startswith("#") else f"#{tag}"
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique_tags.append(tag)

    return " ".join(unique_tags[:max_tags])


# ─── Main Caption Generator ───────────────────────────────────────────────────
def write_caption(idea: Dict, platform: str) -> Dict:
    """Generate caption for a single piece of content"""
    rules = PLATFORM_RULES.get(platform, PLATFORM_RULES["instagram_feed"])

    prompt = f"""Write a caption for Aanya Sharma's {platform.replace('_', ' ')} post.

CONTENT IDEA:
Title: {idea.get('title', '')}
Hook: {idea.get('hook', '')}
Core Message: {idea.get('core_message', '')}
Call to Action: {idea.get('cta', '')}
Pillar: {idea.get('pillar', '')}

PLATFORM RULES:
- Platform: {platform}
- Ideal length: {rules['ideal_length']} characters for caption body (before hashtags)
- Note: {rules['note']}

Write the caption in Aanya's Hinglish voice. Include:
1. Hook (first line, scroll-stopping)
2. Body (the message, 2-4 lines)
3. Golden line (screenshot-worthy insight)
4. CTA

Return a JSON object:
{{
  "caption_body": "the full caption without hashtags",
  "hook_line": "the very first line only",
  "golden_line": "the most quotable/screenshot-worthy line",
  "cta_line": "the call to action line",
  "story_text": "ultra short version for story overlay (max 10 words, Hinglish)",
  "youtube_title": "if youtube_short — SEO-friendly Hindi title (max 60 chars)"
}}"""

    raw = llm(prompt, CAPTION_SYSTEM, temperature=0.9)

    caption_data = {}
    if raw:
        try:
            caption_data = parse_json_response(raw)
        except Exception as e:
            log.warning(f"Caption parse failed: {e}")
            # Use raw as caption body
            caption_data = {
                "caption_body": raw[:rules["max_length"]],
                "hook_line": idea.get("hook", ""),
                "golden_line": idea.get("core_message", ""),
                "cta_line": idea.get("cta", ""),
                "story_text": idea.get("hook", "")[:50]
            }

    # Build hashtags
    hashtags = build_hashtags(idea, platform)

    # Combine caption + hashtags
    caption_body = caption_data.get("caption_body", idea.get("core_message", ""))
    full_caption = f"{caption_body}\n\n{hashtags}"

    result = {
        **caption_data,
        "hashtags": hashtags,
        "full_caption": full_caption,
        "platform": platform,
        "char_count": len(full_caption),
        "idea_title": idea.get("title", "")
    }

    log.success(f"Caption written: {len(full_caption)} chars for {platform}")
    return result


# ─── Carousel Slide Text Generator ───────────────────────────────────────────
def write_carousel_texts(idea: Dict, slides: int = 5) -> List[Dict]:
    """Generate text overlay for each carousel slide"""
    prompt = f"""Write text overlays for a {slides}-slide Instagram carousel by Aanya Sharma.

Topic: {idea.get('title', '')}
Core Message: {idea.get('core_message', '')}
Hook: {idea.get('hook', '')}

Create {slides} slides with text overlay content.
Slide 1: Hook (bold, scroll-stopping)
Slides 2-{slides-1}: Key points/insights (1-2 lines each)
Slide {slides}: Conclusion + CTA

Return a JSON array of {slides} objects:
[{{
  "slide": 1,
  "headline": "big bold text (max 8 words, Hinglish)",
  "subtext": "supporting text (max 15 words, optional)",
  "emoji": "1-2 relevant emojis"
}}]"""

    raw = llm(prompt, CAPTION_SYSTEM)
    try:
        return parse_json_response(raw)
    except:
        return [{"slide": i+1, "headline": f"Point {i+1}", "subtext": "", "emoji": "✨"}
                for i in range(slides)]


# ─── Main ────────────────────────────────────────────────────────────────────
def write_all_captions(media_data: Dict, ideas_data: Dict) -> Dict:
    """Write captions for all media pieces"""
    log.info("=" * 50)
    log.info("STEP 5: Caption Writer Starting")
    log.info("=" * 50)

    media_results = media_data.get("media_results", [])
    captioned = []

    for media in media_results:
        idea = media.get("idea", {})
        platform = idea.get("platform", "instagram_feed")
        content_type = media.get("content_type", "image")

        log.info(f"Writing caption: {idea.get('title', 'Unknown')[:50]}")

        caption = write_caption(idea, platform)

        if content_type == "carousel":
            carousel_texts = write_carousel_texts(idea)
            caption["carousel_texts"] = carousel_texts

        captioned.append({
            **media,
            "caption": caption
        })

    result = {
        "captioned_at": datetime.now().isoformat(),
        "captioned_media": captioned,
        "total": len(captioned)
    }

    save_json(result, f"captioned_{datetime.now().strftime('%Y%m%d')}.json", "data/content_queue")
    log.success(f"Captions written for {len(captioned)} pieces.")
    return result


if __name__ == "__main__":
    dummy_idea = {
        "title": "Log kya kahenge — 5 cheezon ko chodo",
        "pillar": "indian_girl_struggles",
        "platform": "instagram_reel",
        "hook": "Kitni baar tune apna sapna choda? 👀",
        "core_message": "Teri life mein har decision pe society ka opinion kyun chahiye?",
        "cta": "Tag karein woh dost jise yeh sunna chahiye 💕",
        "hashtag_themes": ["logkyakahenge", "indiangirl", "confidence"]
    }
    result = write_caption(dummy_idea, "instagram_reel")
    print(json.dumps(result, indent=2, ensure_ascii=False))
