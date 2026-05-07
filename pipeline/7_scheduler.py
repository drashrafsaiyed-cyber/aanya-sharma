"""
PIPELINE STEP 7 — Content Scheduler
Manages content calendar, assigns optimal IST posting times,
respects all platform rate limits and daily caps.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import pytz

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.storage import save_json, load_json

log = get_logger("scheduler")

IST = pytz.timezone("Asia/Kolkata")
CHARACTER_CONFIG = load_json(os.getenv("CHARACTER_CONFIG", "./character/character_config.json"))
POSTING_SCHEDULE = CHARACTER_CONFIG.get("posting_schedule", {})

QUEUE_FILE = "data/content_queue/post_queue.json"
HISTORY_FILE = "data/analytics/post_history.json"


# ─── Optimal IST Posting Windows ─────────────────────────────────────────────
OPTIMAL_TIMES = {
    "instagram_feed": [
        {"hour": 11, "minute": 0,  "priority": 1},   # 11 AM IST
        {"hour": 19, "minute": 0,  "priority": 2},   # 7 PM IST
        {"hour": 8,  "minute": 30, "priority": 3},   # 8:30 AM IST
    ],
    "instagram_reel": [
        {"hour": 12, "minute": 0,  "priority": 1},   # 12 PM IST
        {"hour": 18, "minute": 0,  "priority": 2},   # 6 PM IST
        {"hour": 21, "minute": 0,  "priority": 3},   # 9 PM IST
    ],
    "instagram_carousel": [
        {"hour": 10, "minute": 0,  "priority": 1},   # 10 AM IST
        {"hour": 20, "minute": 0,  "priority": 2},   # 8 PM IST
    ],
    "instagram_story": [
        {"hour": 7,  "minute": 30, "priority": 1},   # 7:30 AM IST
        {"hour": 21, "minute": 0,  "priority": 2},   # 9 PM IST
        {"hour": 14, "minute": 0,  "priority": 3},   # 2 PM IST
    ],
    "youtube_short": [
        {"hour": 17, "minute": 0,  "priority": 1},   # 5 PM IST
        {"hour": 12, "minute": 0,  "priority": 2},   # 12 PM IST
    ],
    "youtube_video": [
        {"hour": 16, "minute": 0,  "priority": 1},   # 4 PM IST Saturday
    ]
}

# Best days per platform
BEST_DAYS = {
    "instagram_feed":     [0, 2, 4, 6],  # Mon, Wed, Fri, Sun
    "instagram_reel":     [0, 1, 2, 3, 4, 5, 6],  # Daily
    "instagram_carousel": [1, 3, 5],     # Tue, Thu, Sat
    "instagram_story":    [0, 1, 2, 3, 4, 5, 6],  # Daily
    "youtube_short":      [0, 1, 2, 3, 4, 5, 6],  # Daily
    "youtube_video":      [5],           # Saturday
}


# ─── Queue Manager ────────────────────────────────────────────────────────────
def load_queue() -> List[Dict]:
    """Load pending post queue"""
    return load_json(QUEUE_FILE).get("queue", [])


def save_queue(queue: List[Dict]):
    """Persist queue"""
    save_json({"queue": queue, "updated_at": datetime.now().isoformat()},
              "post_queue.json", "data/content_queue")


def load_history() -> List[Dict]:
    """Load posting history"""
    return load_json(HISTORY_FILE).get("history", [])


def get_posts_today(platform: str) -> int:
    """Count posts made today for a platform"""
    history = load_history()
    today = datetime.now(IST).date().isoformat()
    return sum(
        1 for h in history
        if h.get("date") == today and h.get("platform", "").startswith(platform.split("_")[0])
    )


# ─── Time Slot Finder ────────────────────────────────────────────────────────
def find_next_slot(platform: str, target_date: Optional[datetime] = None) -> datetime:
    """
    Find the next optimal IST posting slot for a platform.
    Avoids slots already occupied in the queue.
    """
    now = datetime.now(IST)
    target = target_date or now

    # Try best days first
    best_days = BEST_DAYS.get(platform, [0, 2, 4])
    optimal = OPTIMAL_TIMES.get(platform, [{"hour": 11, "minute": 0, "priority": 1}])

    # Sort by priority
    optimal_sorted = sorted(optimal, key=lambda x: x["priority"])

    # Load current queue to avoid conflicts
    current_queue = load_queue()
    taken_slots = {q.get("scheduled_time") for q in current_queue}

    # Look up to 7 days ahead
    for day_offset in range(7):
        check_date = target + timedelta(days=day_offset)
        weekday = check_date.weekday()

        # Prefer best days
        if weekday not in best_days and day_offset < 3:
            continue

        for slot in optimal_sorted:
            slot_time = check_date.replace(
                hour=slot["hour"],
                minute=slot["minute"],
                second=0, microsecond=0,
                tzinfo=IST
            )
            slot_str = slot_time.isoformat()

            if slot_time > now and slot_str not in taken_slots:
                return slot_time

    # Fallback: tomorrow at 11 AM
    fallback = (now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
    return fallback


# ─── Post Scheduler ───────────────────────────────────────────────────────────
def schedule_content(production_ready: List[Dict]) -> List[Dict]:
    """
    Assign posting times to all approved content.
    Respects platform limits and optimal windows.
    """
    log.info(f"Scheduling {len(production_ready)} pieces of content...")

    queue = load_queue()
    scheduled = []

    # Track slots per platform today
    platform_slots_used = {}

    for item in production_ready:
        idea = item.get("idea", {})
        platform = idea.get("platform", "instagram_feed")

        # Check daily platform limits
        posts_today = get_posts_today(platform)
        slots_today = platform_slots_used.get(platform, 0)
        total_today = posts_today + slots_today

        daily_limits = {
            "instagram": 4,    # total across IG
            "youtube": 2,      # total across YT
        }
        platform_family = platform.split("_")[0]
        limit = daily_limits.get(platform_family, 3)

        if total_today >= limit:
            log.warning(f"Daily limit reached for {platform_family} — scheduling for tomorrow")
            next_slot = find_next_slot(platform, datetime.now(IST) + timedelta(days=1))
        else:
            next_slot = find_next_slot(platform)
            platform_slots_used[platform] = slots_today + 1

        # Build queue item
        queue_item = {
            "id": f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(queue)}",
            "idea_title": idea.get("title", "Unknown"),
            "platform": platform,
            "content_type": item.get("content_type", "image"),
            "scheduled_time": next_slot.isoformat(),
            "scheduled_date": next_slot.strftime("%Y-%m-%d"),
            "scheduled_time_ist": next_slot.strftime("%I:%M %p IST"),
            "caption": item.get("caption", {}),
            "media": {
                "image": item.get("image", {}).get("local_path"),
                "video": item.get("video", {}).get("local_path"),
                "thumbnail": item.get("thumbnail", {}).get("local_path"),
                "carousel_slides": [
                    s.get("local_path")
                    for s in (item.get("carousel", {}) or {}).get("slides", [])
                ] if item.get("carousel") else None
            },
            "status": "scheduled",
            "consistency_report": item.get("consistency_report", {})
        }

        queue.append(queue_item)
        scheduled.append(queue_item)
        log.success(f"Scheduled: {idea.get('title', 'Unknown')[:40]} → {queue_item['scheduled_time_ist']} on {queue_item['scheduled_date']}")

    save_queue(queue)
    log.success(f"Scheduling complete. {len(scheduled)} posts queued.")
    return scheduled


# ─── Content Calendar View ────────────────────────────────────────────────────
def get_weekly_calendar() -> Dict:
    """Get a weekly view of scheduled content"""
    queue = load_queue()
    today = datetime.now(IST).date()
    week_end = today + timedelta(days=7)

    calendar = {}
    for item in queue:
        if item.get("status") == "scheduled":
            date_str = item.get("scheduled_date", "")
            try:
                post_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if today <= post_date <= week_end:
                    day_name = post_date.strftime("%A, %d %B")
                    if day_name not in calendar:
                        calendar[day_name] = []
                    calendar[day_name].append({
                        "time": item.get("scheduled_time_ist"),
                        "platform": item.get("platform"),
                        "title": item.get("idea_title", "")[:50],
                        "type": item.get("content_type")
                    })
            except:
                pass

    return calendar


def get_due_posts() -> List[Dict]:
    """Get posts that are due to be published now (within 5 min window)"""
    queue = load_queue()
    now = datetime.now(IST)
    due = []

    for item in queue:
        if item.get("status") != "scheduled":
            continue
        try:
            scheduled = datetime.fromisoformat(item["scheduled_time"])
            if scheduled.tzinfo is None:
                scheduled = IST.localize(scheduled)
            diff = (now - scheduled).total_seconds()
            if -60 <= diff <= 300:  # 1 min early to 5 min late window
                due.append(item)
        except Exception as e:
            log.warning(f"Time parse error: {e}")

    return due


if __name__ == "__main__":
    # Show weekly calendar
    calendar = get_weekly_calendar()
    print(json.dumps(calendar, indent=2, ensure_ascii=False))
