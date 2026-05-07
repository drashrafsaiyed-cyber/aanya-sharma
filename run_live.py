"""
AANYA SHARMA — Live Content Generator
Runs right now with just Groq + Pollinations (both free)
Generates real content + real images
"""
import os, sys, json, time, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

PYTHON_OK = sys.version_info >= (3, 10)

# ── Terminal colors ───────────────────────────────────────────────────────────
R = "\033[0m"
BOLD = "\033[1m"
PINK = "\033[95m"
CYAN = "\033[96m"
YLW  = "\033[93m"
GRN  = "\033[92m"
DIM  = "\033[2m"
RED  = "\033[91m"

def h1(t):  print(f"\n{BOLD}{PINK}{'═'*58}\n  {t}\n{'═'*58}{R}")
def h2(t):  print(f"\n{BOLD}{CYAN}{'─'*58}\n  {t}\n{'─'*58}{R}")
def ok(t):  print(f"{GRN}  ✅ {t}{R}")
def info(t):print(f"{CYAN}  ➤  {t}{R}")
def out(t): print(f"{YLW}{t}{R}")
def err(t): print(f"{RED}  ✗  {t}{R}")
def dim(t): print(f"{DIM}  {t}{R}")

# ── Groq LLM ─────────────────────────────────────────────────────────────────
def groq(prompt, system="", temp=0.92):
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        msgs = ([{"role":"system","content":system}] if system else []) + \
               [{"role":"user","content":prompt}]
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs, temperature=temp, max_tokens=1800
        )
        return r.choices[0].message.content
    except Exception as e:
        err(f"Groq error: {e}")
        return ""

# ── Aanya's voice ─────────────────────────────────────────────────────────────
VOICE = """You ARE Aanya Sharma — 22-year-old Indian girl. National Crush.

PERSONALITY:
- For BOYS: dream girlfriend speaking directly to them — warm, intimate, real
- For GIRLS: most beautiful bestie — no judgment, full hype, she gets it
- SAME words hit BOTH → gender-neutral Hinglish: "yaar" "tu" "tujhe"
- She CONFIDES. She HYPES. She never lectures.
- Mid-conversation energy: "Yaar sun—" "Ek baat poochu?" "Honestly?"
- Emojis like she actually types: 👀 ✨ 💕 😭 🔥 👑 🌸

NEVER: "girls listen" / "ladies" / big sister tone / corporate motivation"""

# ── Image via Pollinations ────────────────────────────────────────────────────
def gen_image(prompt_text, filename, w=1080, h=1350, seed=None):
    import requests
    encoded = urllib.parse.quote(prompt_text[:450])
    s = seed or int(time.time()) % 99999
    url = (f"https://image.pollinations.ai/prompt/{encoded}"
           f"?width={w}&height={h}&model=flux&nologo=true&seed={s}")
    info(f"Generating image → {filename}")
    try:
        r = requests.get(url, timeout=90)
        if r.ok and len(r.content) > 5000:
            out_dir = Path("output/images")
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / filename
            path.write_bytes(r.content)
            ok(f"Image saved: output/images/{filename}  ({len(r.content)//1024}KB)")
            return str(path)
        else:
            err(f"Pollinations: {r.status_code}")
    except Exception as e:
        err(f"Image gen: {e}")
    return None

# ── Save caption to file ──────────────────────────────────────────────────────
def save_caption(content, filename):
    out_dir = Path("output/captions")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(content, encoding="utf-8")
    ok(f"Caption saved: output/captions/{filename}")

# ─────────────────────────────────────────────────────────────────────────────
# CONTENT PIECES
# ─────────────────────────────────────────────────────────────────────────────

PIECES = [
    {
        "id": "reel_3am",
        "type": "Instagram Reel Script",
        "topic": "3 AM overthinking — yaar tu bhi jaag raha hai?",
        "image_scene": "night_candid",
        "prompt": (
            "Write a 60-second Instagram Reel script for Aanya Sharma.\n"
            "Topic: 3 AM overthinking\n\n"
            "Format (label each section):\n"
            "HOOK (0-3s): First words — stops the scroll cold\n"
            "BODY (3-50s): What she says. Hinglish, conversational, 5-6 punchy lines. "
            "She shares HER OWN 3AM experience first, then speaks to the viewer.\n"
            "CLOSER (50-60s): The one line they'll replay + bestie-style CTA\n\n"
            "Rules: Gender-neutral 'yaar/tu'. Both boys and girls feel it's for them. "
            "She whispers like it's just the two of you. No lecture."
        )
    },
    {
        "id": "feed_behind",
        "type": "Instagram Feed Caption",
        "topic": "Feeling left behind while everyone else has it figured out",
        "image_scene": "morning_terrace",
        "prompt": (
            "Write an Instagram feed caption for Aanya Sharma.\n"
            "Topic: Feeling like everyone else has life figured out and you're behind.\n\n"
            "Structure:\n"
            "LINE 1 (HOOK): Under 125 chars. Bestie opening a real conversation. Hinglish.\n"
            "BODY: 3-4 lines. She shares her OWN story of feeling this first. Then the insight.\n"
            "GOLDEN LINE: One quotable line they'll screenshot. Make it hit hard.\n"
            "CTA: Natural bestie ask — gender-neutral, no 'girls'\n"
            "HASHTAGS: 22 hashtags — mix of Hindi motivation, Indian youth, self-growth, branded #AanyaSharma\n\n"
            "Entire caption in Hinglish. Both boys AND girls should feel she's texting them personally."
        )
    },
    {
        "id": "yt_short_sabotage",
        "type": "YouTube Short Script",
        "topic": "Why you keep self-sabotaging (the real reason)",
        "image_scene": "power_direct",
        "prompt": (
            "Write a YouTube Short script for Aanya Sharma. Under 60 seconds.\n"
            "Topic: Why people self-sabotage — the real psychological reason\n\n"
            "Format:\n"
            "TITLE: Hindi+English mix, SEO, max 60 chars, ends with #Shorts\n"
            "HOOK (0-5s): One sentence. So good they can't scroll.\n"
            "CONTENT (5-52s): Fast, punchy Hinglish. Real Indian example. "
            "She's talking to BOTH boys and girls simultaneously.\n"
            "CLOSER (52-60s): The line they'll replay. Subscribe CTA feels like a bestie asking.\n\n"
            "Energy: Direct eye contact. Intimate. Like she recorded this specifically for the viewer."
        )
    },
    {
        "id": "carousel_confidence",
        "type": "Instagram Carousel — 6 Slides",
        "topic": "5 thoughts silently destroying your confidence + how Aanya reframes them",
        "image_scene": "morning_terrace",
        "prompt": (
            "Write slide text for a 6-slide Instagram Carousel by Aanya Sharma.\n"
            "Topic: '5 thoughts silently destroying your confidence'\n\n"
            "SLIDE 1 — Hook slide:\n"
            "  Headline (bold, 6-8 words, Hinglish, stops the swipe)\n"
            "  Subtext (1 line, makes them want to swipe)\n\n"
            "SLIDES 2-5 — One thought each:\n"
            "  The toxic thought (what we silently tell ourselves — relatable, specific)\n"
            "  Aanya's reframe (her bestie/girlfriend version — warm, punchy, real)\n\n"
            "SLIDE 6 — Save slide:\n"
            "  Closing line (quotable, makes them save the post)\n"
            "  CTA (gender-neutral bestie energy)\n\n"
            "All Hinglish. Gender-neutral. Boys AND girls both feel spoken to."
        )
    },
    {
        "id": "story_gm",
        "type": "Instagram Story Series — 4 Slides",
        "topic": "Good morning — but make it feel like she texted you",
        "image_scene": "morning_terrace",
        "prompt": (
            "Write 4 Instagram Story text overlays for Aanya Sharma — a good morning series.\n\n"
            "Each slide: ultra-short text overlay. Max 10 words. Hinglish. "
            "Gender-neutral. Emojis included.\n"
            "Flow: Wake-up energy → Real talk → Hype → Set the day\n\n"
            "Should feel like she woke up and personally texted YOU.\n"
            "NOT a brand. NOT a motivational page. Just her, talking to you.\n\n"
            "Format each as:\n"
            "SLIDE [N]: [text with emoji]"
        )
    }
]

# ── Image prompts per scene ────────────────────────────────────────────────────
IMAGE_PROMPTS = {
    "morning_terrace": (
        "beautiful indian girl national crush, 22 years old, warm wheatish golden skin, "
        "large expressive kajal-lined brown eyes, long dark silky hair with soft breeze, "
        "full lips warm radiant smile, sharp elegant features, wearing white cotton kurta "
        "with delicate gold jewellery, standing on rooftop terrace at golden hour sunrise, "
        "warm amber sunlight rays, soft bokeh city background, chai cup in hand, "
        "looking directly into camera with playful confident intimate expression, "
        "photorealistic 8k uhd, canon eos r5 f1.8 aperture, magazine editorial quality, "
        "hyperdetailed skin texture, national crush vibes"
    ),
    "night_candid": (
        "beautiful indian girl national crush, 22 years old, warm wheatish skin, "
        "large expressive brown eyes slightly tired but warm and beautiful, "
        "long dark hair loosely tied, wearing cozy beige oversized hoodie, "
        "sitting on bed with warm fairy lights bokeh background, "
        "holding phone looking into camera with genuine late night expression, "
        "soft warm dim intimate lighting, candid real authentic moment, "
        "photorealistic 8k, f1.4 portrait lens, feels like she sent you a 3am voice note, "
        "charming natural beauty no heavy makeup"
    ),
    "power_direct": (
        "beautiful indian girl national crush, 22 years old, warm wheatish glowing skin, "
        "large bold kajal-lined brown eyes looking DIRECTLY into camera with fierce confidence, "
        "long dark hair down, slight powerful smirk, wearing deep maroon ethnic crop top "
        "with minimal gold jewellery, clean minimal warm background, dramatic side lighting, "
        "close-up portrait, feels like she's speaking directly to the viewer personally, "
        "photorealistic 8k uhd, hyperdetailed, canon 85mm f1.2, national crush energy"
    )
}

NEG = ("ugly, deformed, blurry, low quality, cartoon, anime, illustration, "
       "pale skin, blonde hair, blue eyes, western features, caucasian, "
       "nsfw, extra limbs, bad anatomy, watermark, text overlay")

# ─────────────────────────────────────────────────────────────────────────────
def main():
    h1("AANYA SHARMA — LIVE CONTENT GENERATION")
    info(f"Python {sys.version_info.major}.{sys.version_info.minor} | "
         f"Groq: {'✓' if os.getenv('GROQ_API_KEY') else '✗'} | "
         f"Time: {datetime.now().strftime('%I:%M %p')}")
    print()

    all_captions = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Generate all content pieces ──────────────────────────────────────────
    for i, piece in enumerate(PIECES, 1):
        h2(f"[{i}/{len(PIECES)}] {piece['type'].upper()}")
        info(f"Topic: {piece['topic']}")
        print()

        result = groq(piece["prompt"], VOICE)
        if not result:
            err("Groq returned empty — skipping")
            continue

        out(result)
        save_caption(
            f"=== {piece['type']} ===\nTopic: {piece['topic']}\n\n{result}",
            f"{piece['id']}_{ts}.txt"
        )
        all_captions.append({"type": piece["type"], "topic": piece["topic"], "content": result})

        # Small pause between LLM calls
        if i < len(PIECES):
            time.sleep(1)

    # ── Generate images ───────────────────────────────────────────────────────
    h1("GENERATING IMAGES — Pollinations.ai (FREE, FLUX model)")
    info("Using FLUX model — best free quality for Indian portraits\n")

    scenes_done = set()
    img_paths = {}

    for piece in PIECES:
        scene = piece["image_scene"]
        if scene in scenes_done:
            continue
        scenes_done.add(scene)

        prompt_text = IMAGE_PROMPTS[scene]
        fname = f"aanya_{scene}_{ts}.jpg"

        # Dimensions based on scene
        w, h = (1080, 1350)  # default portrait
        if scene == "power_direct":
            w, h = 1080, 1350
        elif scene == "night_candid":
            w, h = 1080, 1920  # reel format

        path = gen_image(prompt_text, fname, w=w, h=h, seed=42 + len(scenes_done))
        if path:
            img_paths[scene] = path
        time.sleep(3)  # Pollinations rate limit

    # ── Save full session log ─────────────────────────────────────────────────
    session = {
        "generated_at": datetime.now().isoformat(),
        "content_pieces": all_captions,
        "images": img_paths,
        "character": "Aanya Sharma",
        "voice": "National Crush | Dual Audience Boys+Girls | Hinglish"
    }
    Path("output").mkdir(exist_ok=True)
    Path(f"output/session_{ts}.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Final summary ─────────────────────────────────────────────────────────
    h1("DONE — SESSION SUMMARY")
    ok(f"{len(all_captions)} content pieces generated")
    ok(f"{len(img_paths)} images created")
    ok(f"All saved in: output/")
    print()
    print(f"{BOLD}  📁 output/captions/  → All scripts & captions{R}")
    print(f"{BOLD}  📁 output/images/    → Generated images{R}")
    print(f"{BOLD}  📄 output/session_{ts}.json → Full session{R}")
    print()
    info("Next: Add Instagram + YouTube credentials to .env → run python orchestrator.py")
    print()

    # Auto-open output folder on Windows
    try:
        import subprocess
        subprocess.Popen(['explorer', str(Path('output').resolve())])
    except:
        pass

if __name__ == "__main__":
    main()
