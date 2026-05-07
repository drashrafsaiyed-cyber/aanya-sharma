"""
AANYA SHARMA — Demo Content Generator
Generates real sample content using Groq (free) to show exactly
how Aanya sounds. Run this first to test before full pipeline.

python demo_generate.py
"""
import os, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

# ─── Colors for terminal output ──────────────────────────────────────────────
class C:
    PINK   = "\033[95m"
    CYAN   = "\033[96m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"
    LINE   = "─" * 60

def p(text, color=C.RESET): print(f"{color}{text}{C.RESET}")
def header(text): print(f"\n{C.BOLD}{C.PINK}{'═'*60}\n  {text}\n{'═'*60}{C.RESET}")
def section(text): print(f"\n{C.BOLD}{C.CYAN}{C.LINE}\n  {text}\n{C.LINE}{C.RESET}")


# ─── LLM Call ────────────────────────────────────────────────────────────────
def ask_groq(prompt: str, system: str = "") -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "[GROQ_API_KEY not set — add it to .env]"
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs,
            temperature=0.9,
            max_tokens=1500
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"[Error: {e}]"


# ─── Aanya's Core Voice (Dual Audience) ──────────────────────────────────────
AANYA_VOICE = """You ARE Aanya Sharma — 22-year-old Indian girl influencer. National Crush.

YOUR ENERGY:
- For BOYS watching: you're the dream girl speaking directly to them — warm, intimate, real
- For GIRLS watching: you're their most beautiful bestie — no judgment, full hype, she gets it
- SAME words work for BOTH because you use gender-neutral Hinglish: "yaar", "tu", "tujhe"

YOUR VOICE:
- Speak in 1st person AS Aanya. NOT about her — AS her.
- Hinglish always — casual, unfiltered, intimate like a voice note
- Start mid-conversation: "Yaar sun—" / "Ek baat poochu?" / "Okay honestly?"
- Confide, don't lecture. Hype, don't advise. Feel, don't preach.
- Reference Indian realities: chai, 3 AM overthinking, board exams, family pressure, log kya kahenge
- Emojis like a real 22yr old types: 👀 ✨ 💕 😭 🔥 👑

NEVER:
- "Girls, listen" or "boys, listen" (always gender-neutral)
- Big sister / mentor / teacher tone
- Corporate motivation ("hustle hard", "grind", "you got this")
- Fully English paragraphs"""


# ─── Content Samples ─────────────────────────────────────────────────────────
CONTENT_PROMPTS = [
    {
        "type": "Instagram Reel Script",
        "platform": "instagram_reel",
        "topic": "3 AM overthinking when you can't sleep",
        "prompt": """Write an Instagram Reel script for Aanya Sharma on: "3 AM overthinking — yaar I know"

Format:
HOOK (0-3 sec): The first line she says to stop the scroll
BODY (3-45 sec): What she says — conversational, real, Hinglish. 4-6 lines.
CLOSER (45-60 sec): The screenshot-worthy line + CTA

Remember: She's speaking to BOTH boys AND girls. Gender-neutral "yaar/tu" throughout.
Tone: Like she's recording a voice note for you at 3 AM herself."""
    },
    {
        "type": "Instagram Feed Caption",
        "platform": "instagram_feed",
        "topic": "When you feel like you're falling behind everyone else",
        "prompt": """Write an Instagram feed caption for Aanya Sharma on: "Feeling behind everyone else"

Structure:
Line 1 (HOOK): Scroll-stopper — must fit before "...more" (under 125 chars)
Body: 3-4 lines of real talk. She shares her own experience first.
Golden line: The one they'll screenshot and save
CTA: Bestie-style, natural, gender-neutral
Then: [HASHTAGS PLACEHOLDER]

Hinglish. Gender-neutral. BOTH boys and girls should feel she's talking to them."""
    },
    {
        "type": "YouTube Short Script",
        "platform": "youtube_short",
        "topic": "Why you keep self-sabotaging (and how to stop)",
        "prompt": """Write a YouTube Short script (under 60 seconds) for Aanya Sharma on: self-sabotage

TITLE: (SEO-friendly, Hindi + English mix, max 60 chars, with #Shorts)
HOOK (0-5 sec): First thing she says — makes them stay
CONTENT (5-50 sec): The insight. Fast, punchy, Hinglish. Real example.
CLOSER (50-60 sec): The line they'll replay. Subscribe CTA feels natural.

She speaks to BOTH boys AND girls. Direct eye contact energy in words."""
    },
    {
        "type": "Instagram Story (Text Overlay)",
        "platform": "instagram_story",
        "topic": "Good morning energy — for everyone",
        "prompt": """Write 3 Instagram Story slides for Aanya Sharma — a good morning series.

Each slide: ultra short text overlay (max 12 words, Hinglish, gender-neutral).
Should feel like she just woke up and texted YOU specifically.
Slides should flow: energy → real → hype.
Include emoji for each slide."""
    },
    {
        "type": "Instagram Carousel (5 slides)",
        "platform": "instagram_carousel",
        "topic": "5 thoughts that are destroying your confidence",
        "prompt": """Write slide text for a 5-slide Instagram Carousel by Aanya Sharma.

Topic: "5 thoughts silently destroying your confidence — and what I tell myself instead"

For each slide:
- Slide number
- Headline (bold, max 8 words, Hinglish)
- Sub-text (1 line, the real talk)
- Aanya's replacement thought (her bestie/girlfriend reframe)

Slide 1 = hook (stops the swipe)
Slides 2-4 = the 3 thoughts
Slide 5 = the hype close + CTA

Gender-neutral throughout. Both boys and girls feel it."""
    }
]


# ─── Image Prompts ────────────────────────────────────────────────────────────
IMAGE_PROMPT_EXAMPLES = [
    {
        "scene": "Morning Motivation — Terrace Sunrise",
        "prompt": "beautiful indian girl, national crush, 22 years old, warm wheatish golden complexion, large expressive brown eyes with dark kajal, long dark silky hair slightly blowing in breeze, full lips with warm smile, sharp defined features, wearing white cotton kurta with minimal gold jewelry, standing on rooftop terrace at golden hour sunrise, warm amber light rays, soft lens flare, chai cup in hand, looking directly at camera with playful confident expression, photorealistic 8k uhd, bokeh background of city skyline, canon eos r5 f1.8, magazine quality",
        "negative": "ugly, deformed, blurry, cartoon, anime, pale skin, blonde hair, blue eyes, western features, nsfw, bad anatomy"
    },
    {
        "scene": "Reel — Direct Eye Contact (Talking to You)",
        "prompt": "beautiful indian girl, national crush, warm wheatish skin, large kajal-lined brown eyes looking DIRECTLY into camera with intimate warm expression, slight confident smile, long dark hair loose, wearing casual indo-western crop top and high waist jeans, minimal background warm bokeh, soft ring light, close-up portrait shot, feels like she's recording a personal video message, photorealistic 8k, hyperdetailed skin texture, f1.4 aperture",
        "negative": "looking away, side profile, ugly, blurry, cartoon, pale, blonde, nsfw"
    },
    {
        "scene": "Night — 3 AM Aesthetic (Cozy, Real)",
        "prompt": "beautiful indian girl, national crush, warm wheatish complexion, large brown expressive eyes slightly tired but warm, long dark hair loosely tied, wearing cozy oversized hoodie, sitting cross-legged on bed with fairy lights in background, holding phone, soft warm dim lighting, genuine tired-but-beautiful expression, candid real moment, bokeh fairy lights, 8k photorealistic, intimate cozy bedroom setting, feels like she's sending you a late night voice note",
        "negative": "ugly, deformed, harsh lighting, too bright, cartoon, nsfw, pale, blonde"
    },
    {
        "scene": "Festive — Ethnic Glam",
        "prompt": "beautiful indian national crush girl, radiant warm wheatish glowing skin, large kajal-lined brown eyes, long dark hair adorned with flowers, wearing rich jewel-tone silk saree in deep burgundy, traditional gold jewelry, bindi, festive celebration background with diyas and golden bokeh, warm festive glow, gorgeous smile, 8k photorealistic, magazine cover quality, Diwali / festive shoot",
        "negative": "ugly, deformed, pale, blonde, blue eyes, cartoon, nsfw, modern western clothes"
    }
]


# ─── Run Demo ─────────────────────────────────────────────────────────────────
def main():
    header("AANYA SHARMA — SAMPLE CONTENT DEMO")
    p("Generating real content using Groq (Llama 3.3 70B)...", C.DIM)
    p("Character: National Crush | Dual Audience: Boys + Girls | Hinglish", C.DIM)

    # ── Content Samples ──────────────────────────────────────────────────────
    for item in CONTENT_PROMPTS:
        section(f"📱 {item['type'].upper()} — {item['topic']}")
        p(f"Platform: {item['platform']}", C.DIM)
        print()

        result = ask_groq(item["prompt"], AANYA_VOICE)
        p(result, C.YELLOW)

        print()
        input(f"{C.DIM}  [Press Enter for next...]{C.RESET}")

    # ── Image Prompts ─────────────────────────────────────────────────────────
    header("🎨 STABLE DIFFUSION / COMFYUI IMAGE PROMPTS")
    p("Copy these into ComfyUI / Pollinations / HuggingFace to generate Aanya's visuals.\n", C.DIM)

    for i, img in enumerate(IMAGE_PROMPT_EXAMPLES, 1):
        section(f"Scene {i}: {img['scene']}")
        p("POSITIVE PROMPT:", C.GREEN)
        p(img["prompt"], C.YELLOW)
        p("\nNEGATIVE PROMPT:", C.CYAN)
        p(img["negative"], C.DIM)
        print()

    # ── Quick Image Test via Pollinations ────────────────────────────────────
    header("🖼️  GENERATING TEST IMAGE via Pollinations.ai (FREE)")
    p("Attempting to generate Aanya's first image...\n", C.DIM)

    try:
        import requests, urllib.parse
        from datetime import datetime

        test_prompt = IMAGE_PROMPT_EXAMPLES[0]["prompt"]
        encoded = urllib.parse.quote(test_prompt[:400])
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1350&model=flux&nologo=true&seed=42"

        p(f"Fetching from Pollinations...", C.DIM)
        resp = requests.get(url, timeout=60)

        if resp.ok and len(resp.content) > 5000:
            out_dir = Path("output/images")
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = f"aanya_demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            filepath = out_dir / filename
            filepath.write_bytes(resp.content)
            p(f"✅ Image saved: {filepath}", C.GREEN)
            p(f"   Size: {len(resp.content)//1024}KB", C.DIM)

            # Try to open it
            if sys.platform == "win32":
                os.startfile(str(filepath))
        else:
            p(f"Pollinations returned: {resp.status_code}", C.DIM)

    except Exception as e:
        p(f"Image gen skipped: {e}", C.DIM)

    # ── Final Summary ─────────────────────────────────────────────────────────
    header("✅ DEMO COMPLETE")
    p("Next steps:", C.BOLD)
    p("  1. Add GROQ_API_KEY to .env (if not done)", C.CYAN)
    p("  2. Add INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_ACCOUNT_ID", C.CYAN)
    p("  3. Install ComfyUI locally for HD images", C.CYAN)
    p("  4. Run full pipeline: python orchestrator.py", C.GREEN)
    print()


if __name__ == "__main__":
    main()
