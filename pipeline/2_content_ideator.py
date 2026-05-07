"""
PIPELINE STEP 2 — Content Ideator
Uses Groq (Llama 3.3 70B) → fallback Gemini 2.0 Flash → fallback Ollama
Generates viral content ideas for Aanya Sharma matching trending topics
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.rate_limiter import get_limiter
from utils.storage import save_json, load_json

log = get_logger("content_ideator")
limiter = get_limiter()

CHARACTER_CONFIG = load_json(os.getenv("CHARACTER_CONFIG", "./character/character_config.json"))


# ─── LLM Client Factory ─────────────────────────────────────────────────────
def call_groq(prompt: str, system: str = "") -> Optional[str]:
    """Call Groq API (Llama 3.3 70B — fastest free LLM)"""
    if not limiter.acquire("groq"):
        return None
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.85,
            max_tokens=2048
        )
        return response.choices[0].message.content
    except Exception as e:
        log.warning(f"Groq failed: {e}")
        return None


def call_gemini(prompt: str, system: str = "") -> Optional[str]:
    """Call Gemini 2.0 Flash (fallback)"""
    if not limiter.acquire("gemini"):
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        log.warning(f"Gemini failed: {e}")
        return None


def call_ollama(prompt: str, system: str = "") -> Optional[str]:
    """Call local Ollama (last resort — always free, always local)"""
    try:
        import requests
        payload = {
            "model": "llama3.2",
            "prompt": f"{system}\n\n{prompt}" if system else prompt,
            "stream": False
        }
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=60)
        if r.ok:
            return r.json().get("response", "")
    except Exception as e:
        log.warning(f"Ollama failed: {e}")
    return None


def llm(prompt: str, system: str = "") -> str:
    """Try LLMs in cascade: Groq → Gemini → Ollama"""
    result = call_groq(prompt, system)
    if result:
        log.debug("Used: Groq")
        return result

    result = call_gemini(prompt, system)
    if result:
        log.debug("Used: Gemini")
        return result

    result = call_ollama(prompt, system)
    if result:
        log.debug("Used: Ollama")
        return result

    log.error("All LLMs failed!")
    return ""


# ─── Aanya's System Prompt ───────────────────────────────────────────────────
AANYA_SYSTEM = """You are the content strategy brain for AANYA SHARMA — an AI Indian girl influencer.

CHARACTER PROFILE:
- Name: Aanya Sharma, 22-year-old Indian girl
- Niche: Motivational / Mindset / Self-Growth for Indian youth
- Target audience: ALL Indian youth 16-28 — both boys AND girls equally
  → BOYS feel: "the most beautiful girl is speaking directly to me, she gets me"
  → GIRLS feel: "she's my most stunning bestie who never judges and always hypes"
- Language: Hinglish — gender-neutral "yaar" / "tu" / "tujhe" so EVERYONE feels addressed
- Personality: National Crush + Best Friend / Dream Girlfriend energy
  → NOT a wise big sister. NOT a mentor. NOT preachy.
  → She confides. She hypes. She teases lovingly. She makes you feel SEEN.
  → Makes BOTH boys and girls feel like she's talking to them personally.
- Platforms: Instagram (Reels, Feed, Stories, Carousel) + YouTube (Shorts)
- Tone: Intimate, real, mid-conversation — like a voice note from the most beautiful person you know.
- Catchphrases: "Yaar tu serious nahi le raha/rahi khud ko, but I am 👀", "Tu amazing hai — bas tujhe abhi tak pata nahi ✨", "Teri mehnat tera crown hai 👑", "Main hoon na. Hamesha. 🌸"

DUAL AUDIENCE CONTENT RULES:
- Use "yaar", "tu", "tujhe" — gender-neutral, intimate for BOTH boys and girls
- Content themes that hit both: self-doubt, career fear, heartbreak, family pressure, 3 AM thoughts, confidence
- Boys watch because: she's warm, real, direct — feels like she's talking to HIM
- Girls watch because: she's relatable, non-judgmental, hypes them up like a true bestie
- Open like a private conversation — "Yaar sun—" / "Ek baat poochu?" / "Tujhse kuch honestly—"
- NEVER gender-specific openers like "girls, listen" or "ladies" — always inclusive
- CTA: "tag kar yaar jise yeh sunna chahiye" — works for anyone tagging anyone
- Avoid politics, religion controversy, body shaming"""


# ─── Content Idea Generator ──────────────────────────────────────────────────
def generate_content_ideas(trends: List[Dict], count: int = 7) -> List[Dict]:
    """Generate viral content ideas based on trending topics"""
    log.info(f"Generating {count} content ideas from {len(trends)} trends...")

    # Format top trends for the prompt
    trend_text = "\n".join([
        f"- {t.get('topic', 'Unknown')} (score: {t.get('relevance_score', 0):.0f})"
        for t in trends[:10]
    ])

    pillar_names = list(CHARACTER_CONFIG.get("content_pillars", {}).keys())
    catchphrases = CHARACTER_CONFIG.get("personality", {}).get("catchphrases", [])

    prompt = f"""Based on these TRENDING topics in India today:
{trend_text}

Generate {count} viral content ideas for Aanya Sharma's Instagram + YouTube.

For EACH idea, output a JSON object with these fields:
{{
  "title": "catchy content title",
  "pillar": "which content pillar (morning_mindset/mindset_shifts/indian_girl_struggles/success_hustle/self_love_glow/festival_culture)",
  "platform": "instagram_reel OR instagram_feed OR instagram_carousel OR youtube_short",
  "hook": "the first line that stops the scroll (Hinglish, punchy, max 15 words)",
  "core_message": "the main message or insight (2-3 sentences)",
  "format": "reel_talking_head OR quote_image OR carousel_tips OR b_roll_reel",
  "viral_angle": "WHY this will go viral — what emotion does it trigger",
  "trending_topic_used": "which trend from the list this leverages",
  "visual_concept": "brief visual description for image generation",
  "cta": "call-to-action for the post",
  "hashtag_themes": ["theme1", "theme2", "theme3"]
}}

Return ONLY a JSON array of {count} idea objects. No extra text.
Prioritize ideas that will resonate with Indian girls 16-28 facing career pressure, family expectations, self-doubt."""

    raw = llm(prompt, AANYA_SYSTEM)

    if not raw:
        log.error("LLM returned empty response")
        return _fallback_ideas()

    # Parse JSON
    try:
        # Strip markdown code blocks if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```")

        ideas = json.loads(raw)
        log.success(f"Generated {len(ideas)} content ideas")
        return ideas

    except json.JSONDecodeError as e:
        log.error(f"Failed to parse LLM response as JSON: {e}")
        log.debug(f"Raw response: {raw[:500]}")
        return _fallback_ideas()


def _fallback_ideas() -> List[Dict]:
    """Hardcoded fallback ideas if LLM fails"""
    return [
        {
            "title": "Log kya kahenge — yaar ab enough hai",
            "pillar": "indian_girl_struggles",
            "platform": "instagram_reel",
            "hook": "Yaar, ek baat poochu? Tu kitni baar ruk gayi kyunki kisi aur ko bura lagta? 👀",
            "core_message": "Main bhi ruki thi. Ek baar nahi — kai baar. Par ek din samjhi: jo log comment karte hain, woh teri life jeete nahi. Tu jeeti hai. Toh decision bhi tera.",
            "format": "reel_talking_head",
            "viral_angle": "Feels like a bestie confiding, not a speech — will get mass saves and tags",
            "trending_topic_used": "log kya kahenge",
            "visual_concept": "Aanya direct eye contact with camera, casual ethnic top, warm light, slight smile — mid-conversation feel",
            "cta": "Tag kar yaar jise yeh sunna chahiye 💕",
            "hashtag_themes": ["logkyakahenge", "indiangirl", "confidence"]
        },
        {
            "title": "Subah ki routine jo actually kaam karti hai — bestie version",
            "pillar": "morning_mindset",
            "platform": "instagram_reel",
            "hook": "Okay sun, yeh '5 AM wale' reels dekh dekh ke frustrated ho? Mujhe bhi hoti thi. 😭",
            "core_message": "Toh maine apni khud ki routine banayi. 30 minute. Chai included. Aur honestly? Life badli. Tujhe bhi share karna tha.",
            "format": "b_roll_reel",
            "viral_angle": "Anti-toxic-productivity angle + relatable + bestie sharing her secret routine",
            "trending_topic_used": "morning routine india",
            "visual_concept": "Aanya on terrace, sunrise, white ethnic top, chai cup, laughing candidly at camera",
            "cta": "Save kar yaar, kal try karte hain saath mein ☀️",
            "hashtag_themes": ["morningroutine", "selfgrowth", "indiangirl"]
        }
    ]


# ─── Idea Ranker ─────────────────────────────────────────────────────────────
def rank_and_select_ideas(ideas: List[Dict], top_n: int = 3) -> List[Dict]:
    """Use LLM to rank ideas by predicted virality"""
    log.info(f"Ranking {len(ideas)} ideas by virality potential...")

    ideas_text = json.dumps(ideas, ensure_ascii=False, indent=2)

    prompt = f"""Here are {len(ideas)} content ideas for Aanya Sharma (Indian motivational influencer):

{ideas_text}

Rank these ideas from MOST to LEAST likely to go viral on Instagram/YouTube in India.
Consider:
1. Emotional resonance with Indian youth (16-28)
2. Shareability (will they tag a friend?)
3. Platform algorithm favorability (saves, shares, comments)
4. Trend alignment
5. Originality

Return ONLY a JSON array of the top {top_n} idea objects in ranked order (best first).
Keep all original fields. Add a "virality_score" (0-100) and "why_viral" (one sentence) to each."""

    raw = llm(prompt, AANYA_SYSTEM)

    if not raw:
        return ideas[:top_n]

    try:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```")

        ranked = json.loads(raw)
        log.success(f"Top idea: {ranked[0].get('title', 'N/A')} (score: {ranked[0].get('virality_score', '?')})")
        return ranked

    except Exception as e:
        log.warning(f"Ranking parse failed: {e} — using original order")
        return ideas[:top_n]


# ─── Main ────────────────────────────────────────────────────────────────────
def ideate(trends_data: Dict) -> Dict:
    """Full content ideation pipeline"""
    log.info("=" * 50)
    log.info("STEP 2: Content Ideator Starting")
    log.info("=" * 50)

    trends = trends_data.get("top_trends", [])
    if not trends:
        log.warning("No trends provided — using seed topics")
        trends = [{"topic": t, "relevance_score": 50} for t in [
            "log kya kahenge", "morning routine", "success mindset india"
        ]]

    # Generate 7 ideas, rank to top 3
    all_ideas = generate_content_ideas(trends, count=7)
    top_ideas = rank_and_select_ideas(all_ideas, top_n=3)

    result = {
        "ideated_at": datetime.now().isoformat(),
        "trends_used": len(trends),
        "total_ideas_generated": len(all_ideas),
        "selected_ideas": top_ideas,
        "all_ideas": all_ideas
    }

    save_json(result, f"ideas_{datetime.now().strftime('%Y%m%d')}.json", "data/content_queue")
    log.success(f"Content ideation complete. {len(top_ideas)} ideas selected for production.")

    return result


if __name__ == "__main__":
    # Test with dummy trends
    dummy_trends = {
        "top_trends": [
            {"topic": "log kya kahenge", "relevance_score": 90},
            {"topic": "morning routine india", "relevance_score": 85},
            {"topic": "exam stress india", "relevance_score": 80},
            {"topic": "self confidence girl", "relevance_score": 75},
        ]
    }
    result = ideate(dummy_trends)
    print(json.dumps(result, indent=2, ensure_ascii=False))
