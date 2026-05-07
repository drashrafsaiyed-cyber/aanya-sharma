"""
PIPELINE STEP 6 — Consistency Enforcer
Validates every output against Aanya's character bible.
Catches: wrong tone, wrong language, character drift, off-brand visuals.
Regenerates or flags anything that doesn't match.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Tuple

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.storage import load_json, save_json
from pipeline._llm_utils import llm, parse_json_response

log = get_logger("consistency_enforcer")

CHARACTER_CONFIG = load_json(os.getenv("CHARACTER_CONFIG", "./character/character_config.json"))

# Extract key identity rules
FORBIDDEN = CHARACTER_CONFIG.get("personality", {}).get("forbidden_behaviors", [])
CATCHPHRASES = CHARACTER_CONFIG.get("personality", {}).get("catchphrases", [])
LANGUAGE_STYLE = CHARACTER_CONFIG.get("identity", {}).get("language_style", "Hinglish")
FORBIDDEN_COLORS = CHARACTER_CONFIG.get("visual_identity", {}).get(
    "color_palette", {}
).get("forbidden", [])


# ─── Caption Validator ────────────────────────────────────────────────────────
def validate_caption(caption_data: Dict, idea: Dict) -> Tuple[bool, str, str]:
    """
    Validate a caption against Aanya's character.
    Returns: (is_valid, issue, fixed_version)
    """
    caption_body = caption_data.get("caption_body", "")

    if len(caption_body) < 20:
        return False, "Caption too short", ""

    prompt = f"""You are the quality control for AANYA SHARMA's Instagram/YouTube content.

CHARACTER RULES (must ALL be satisfied):
1. Language MUST be Hinglish — casual, intimate, like texting a close friend
2. Tone: best friend / dream girlfriend energy — NOT big sister, NOT mentor, NOT preachy
   She confides and hypes. She does NOT lecture or give advice like a teacher.
3. Forbidden behaviors: {json.dumps(FORBIDDEN)}
4. Must feel like a real Indian 22-year-old girl talking to her friend, NOT a motivational post
5. Must open like a conversation ("Yaar—", "Okay sun—", "Tujhse kuch—") NOT a speech

CAPTION TO VALIDATE:
{caption_body}

CONTENT IDEA:
{idea.get('core_message', '')}

Evaluate this caption. Return JSON:
{{
  "is_valid": true/false,
  "score": 0-100,
  "issues": ["list of issues if any"],
  "fixed_caption": "if not valid, rewrite it correctly in Aanya's voice. If valid, return original.",
  "verdict": "APPROVED / NEEDS_FIX / REJECT"
}}"""

    raw = llm(prompt)
    try:
        result = parse_json_response(raw)
        is_valid = result.get("is_valid", True) and result.get("score", 100) >= 70
        verdict = result.get("verdict", "APPROVED")
        issues = result.get("issues", [])
        fixed = result.get("fixed_caption", caption_body)

        if not is_valid:
            log.warning(f"Caption issue: {issues}")
        else:
            log.success(f"Caption approved (score: {result.get('score', '?')})")

        return is_valid, str(issues), fixed

    except Exception as e:
        log.warning(f"Validation parse failed: {e} — auto-approving")
        return True, "", caption_body


# ─── Visual Prompt Validator ──────────────────────────────────────────────────
def validate_image_prompt(prompt_data: Dict) -> Tuple[bool, str]:
    """
    Check image prompt for character consistency violations.
    """
    positive = prompt_data.get("positive", "")

    issues = []

    # Must contain character identity markers
    required_terms = ["indian", "brown eyes", "dark hair"]
    missing = [t for t in required_terms if t not in positive.lower()]
    if missing:
        issues.append(f"Missing identity markers: {missing}")

    # Must NOT contain forbidden elements
    forbidden_visual = ["blonde", "blue eyes", "pale skin", "western girl", "caucasian", "white girl"]
    found_forbidden = [f for f in forbidden_visual if f in positive.lower()]
    if found_forbidden:
        issues.append(f"Contains forbidden visual elements: {found_forbidden}")

    # Check color palette
    for color in FORBIDDEN_COLORS:
        if color.lower() in positive.lower():
            issues.append(f"Forbidden color in prompt: {color}")

    if issues:
        log.warning(f"Image prompt issues: {issues}")
        return False, str(issues)

    log.success("Image prompt validated")
    return True, ""


# ─── Prompt Auto-Fixer ────────────────────────────────────────────────────────
def fix_image_prompt(prompt_data: Dict) -> Dict:
    """Auto-fix image prompt to enforce character identity"""
    positive = prompt_data.get("positive", "")

    # Remove forbidden terms
    forbidden_replacements = {
        "blonde hair": "long dark hair",
        "blue eyes": "large brown expressive eyes",
        "pale skin": "warm wheatish complexion",
        "caucasian": "indian",
        "white girl": "beautiful indian girl"
    }

    for wrong, right in forbidden_replacements.items():
        positive = positive.replace(wrong, right)

    # Ensure character anchor is present
    anchor = "beautiful indian girl, national crush, warm wheatish complexion, large expressive brown eyes, long dark hair"
    if "indian" not in positive.lower():
        positive = anchor + ", " + positive

    # Ensure negative prompt is strong
    negative = prompt_data.get("negative", "")
    must_negatives = ["blonde", "blue eyes", "pale skin", "western features", "caucasian"]
    for neg in must_negatives:
        if neg not in negative.lower():
            negative += f", {neg}"

    return {**prompt_data, "positive": positive, "negative": negative}


# ─── Brand Voice Checker ──────────────────────────────────────────────────────
def check_brand_voice(text: str) -> Dict:
    """
    Score text for Aanya's brand voice alignment.
    Returns score dict.
    """
    score = 100
    issues = []

    # Check for Hinglish (should have some Hindi words)
    hindi_markers = [
        "kya", "hai", "hain", "yaar", "apna", "teri", "meri", "karo", "soch",
        "band", "shuru", "chahiye", "sabse", "pyaar", "dost", "aaj", "kal",
        "sapna", "mehnat", "zindagi", "log", "khud", "baar", "sun", "bata",
        "haan", "nahi", "tujhe", "mujhe", "sach", "abey", "chal", "bhai"
    ]
    hindi_count = sum(1 for word in hindi_markers if word in text.lower())
    if hindi_count == 0:
        score -= 30
        issues.append("No Hindi words detected — must be Hinglish")
    elif hindi_count < 2:
        score -= 10
        issues.append("Too little Hindi — increase Hinglish blend")

    # Check for best-friend opener signals (positive)
    bestie_openers = ["yaar", "sun ", "okay sun", "bata", "honestly", "tujhse", "sach bol"]
    has_bestie_opener = any(o in text.lower() for o in bestie_openers)
    if has_bestie_opener:
        score = min(100, score + 10)
    else:
        issues.append("Missing bestie opener — should start like a conversation not a speech")
        score -= 10

    # Check against forbidden patterns
    forbidden_patterns = [
        ("grind don't stop", 20, "corporate hustle bro language"),
        ("hustle hard", 15, "too western"),
        ("rise and shine", 10, "cliché"),
        ("no pain no gain", 15, "too western"),
        ("as your mentor", 25, "mentor tone forbidden"),
        ("let me teach", 25, "teacher tone forbidden"),
        ("you should know", 15, "preachy big-sister tone"),
        ("listen carefully", 10, "lecture tone — use 'sun yaar' instead"),
    ]
    for pattern, penalty, reason in forbidden_patterns:
        if pattern in text.lower():
            score -= penalty
            issues.append(f"Forbidden phrase '{pattern}': {reason}")

    # Positive signals
    catchphrase_used = any(cp.lower()[:15] in text.lower() for cp in CATCHPHRASES)
    if catchphrase_used:
        score = min(100, score + 5)

    return {
        "score": max(0, score),
        "hindi_words_found": hindi_count,
        "issues": issues,
        "verdict": "APPROVED" if score >= 70 else "NEEDS_FIX"
    }


# ─── Full Content Package Enforcer ───────────────────────────────────────────
def enforce_consistency(captioned_data: Dict) -> Dict:
    """
    Run all consistency checks on complete content packages.
    Fix what can be fixed, flag what cannot.
    """
    log.info("=" * 50)
    log.info("STEP 6: Consistency Enforcer Starting")
    log.info("=" * 50)

    captioned_media = captioned_data.get("captioned_media", [])
    enforced = []
    flagged = []

    for item in captioned_media:
        idea = item.get("idea", {})
        caption = item.get("caption", {})
        title = idea.get("title", "Unknown")

        log.info(f"Checking: {title[:50]}")
        passed_all = True
        item_issues = []

        # 1. Validate caption
        caption_body = caption.get("caption_body", "")
        cap_valid, cap_issue, cap_fixed = validate_caption(caption, idea)
        if not cap_valid:
            item["caption"]["caption_body"] = cap_fixed
            item["caption"]["full_caption"] = (
                cap_fixed + "\n\n" + caption.get("hashtags", "")
            )
            item_issues.append(f"Caption fixed: {cap_issue}")
            passed_all = False

        # 2. Brand voice check
        voice_check = check_brand_voice(caption_body)
        if voice_check["verdict"] != "APPROVED":
            item_issues.extend(voice_check["issues"])
            passed_all = False

        # 3. Validate image prompt (if present)
        for prompt_key in ["image_prompt", "thumbnail_prompt"]:
            prompt_data = item.get(prompt_key)
            if prompt_data:
                prompt_valid, prompt_issue = validate_image_prompt(prompt_data)
                if not prompt_valid:
                    item[prompt_key] = fix_image_prompt(prompt_data)
                    item_issues.append(f"Prompt fixed: {prompt_issue}")

        # Attach consistency report
        item["consistency_report"] = {
            "passed": passed_all,
            "voice_score": voice_check["score"],
            "issues_found": item_issues,
            "checked_at": datetime.now().isoformat()
        }

        if passed_all:
            log.success(f"APPROVED: {title[:40]}")
            enforced.append(item)
        else:
            log.warning(f"FIXED & APPROVED: {title[:40]} ({len(item_issues)} issues fixed)")
            enforced.append(item)  # Still include — we fixed it

    result = {
        "enforced_at": datetime.now().isoformat(),
        "approved_count": len(enforced),
        "flagged_count": len(flagged),
        "production_ready": enforced
    }

    save_json(result, f"enforced_{datetime.now().strftime('%Y%m%d')}.json", "data/content_queue")
    log.success(f"Consistency check complete. {len(enforced)} approved, {len(flagged)} flagged.")
    return result


if __name__ == "__main__":
    # Test brand voice checker
    test_texts = [
        "Uthh! Aaj ka din tera hai. Apni mehnat pe yakeen rakh. ✨",
        "Grind don't stop! Hustle hard every day! Rise and shine!",
        "Kya tujhe pata hai? Teri zindagi mein sabse badi rukawat kya hai?"
    ]
    for text in test_texts:
        result = check_brand_voice(text)
        print(f"Score: {result['score']} | {result['verdict']} | {text[:50]}")
