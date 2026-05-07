"""
ORCHESTRATOR — Aanya Sharma AI Influencer System
Master controller that runs the full pipeline.
Can be triggered by: GitHub Actions cron / manual / scheduler daemon.

Usage:
  python orchestrator.py              # full daily pipeline
  python orchestrator.py --post-only  # just check queue and post due items
  python orchestrator.py --analytics  # just run analytics
  python orchestrator.py --status     # show system status
"""
import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger
from utils.rate_limiter import get_limiter

log = get_logger("orchestrator")
limiter = get_limiter()


# ─── Pipeline Imports ─────────────────────────────────────────────────────────
def import_pipeline():
    """Lazy imports to catch missing dependencies gracefully"""
    try:
        from pipeline.trend_scraper import scrape_trends
        from pipeline.content_ideator import ideate
        from pipeline.prompt_generator import generate_prompts
        from pipeline.media_creator import create_media
        from pipeline.caption_writer import write_all_captions
        from pipeline.consistency_enforcer import enforce_consistency
        from pipeline.scheduler import schedule_content
        from pipeline.poster import post_due_items
        from pipeline.analytics import run_analytics, get_ideator_feedback
        return {
            "scrape_trends": scrape_trends,
            "ideate": ideate,
            "generate_prompts": generate_prompts,
            "create_media": create_media,
            "write_all_captions": write_all_captions,
            "enforce_consistency": enforce_consistency,
            "schedule_content": schedule_content,
            "post_due_items": post_due_items,
            "run_analytics": run_analytics,
            "get_ideator_feedback": get_ideator_feedback
        }
    except ImportError as e:
        log.error(f"Import failed: {e}")
        log.info("Run: pip install -r requirements.txt")
        sys.exit(1)


# ─── Full Daily Pipeline ─────────────────────────────────────────────────────
def run_daily_pipeline():
    """
    Full end-to-end content pipeline.
    Runs every day at 06:00 IST via GitHub Actions.
    """
    pipeline = import_pipeline()
    start_time = datetime.now()

    log.info("=" * 60)
    log.info("  AANYA SHARMA — AI INFLUENCER PIPELINE STARTING")
    log.info(f"  {start_time.strftime('%A, %d %B %Y — %I:%M %p')}")
    log.info("=" * 60)

    # Load previous analytics feedback
    feedback = pipeline["get_ideator_feedback"]()
    if feedback:
        log.info(f"Loaded feedback: focus on '{feedback.get('next_week_focus', 'general')}'")

    # ── STEP 1: Scrape Trends ────────────────────────────────────────
    log.info("\n[1/7] Scraping trends...")
    trends_data = pipeline["scrape_trends"]()
    top_trend = trends_data.get("top_trends", [{}])[0].get("topic", "N/A")
    log.success(f"Top trend today: {top_trend}")

    # ── STEP 2: Ideate Content ───────────────────────────────────────
    log.info("\n[2/7] Generating content ideas...")
    # Inject feedback into ideation
    if feedback:
        trends_data["strategy_feedback"] = feedback
    ideas_data = pipeline["ideate"](trends_data)
    n_ideas = len(ideas_data.get("selected_ideas", []))
    log.success(f"Selected {n_ideas} ideas for production")

    if n_ideas == 0:
        log.error("No ideas generated — pipeline aborted")
        return False

    # ── STEP 3: Generate Prompts ─────────────────────────────────────
    log.info("\n[3/7] Building image/video prompts...")
    prompts_data = pipeline["generate_prompts"](ideas_data)
    log.success(f"Prompts ready for {prompts_data.get('total', 0)} content pieces")

    # ── STEP 4: Create Media ─────────────────────────────────────────
    log.info("\n[4/7] Creating images and videos...")
    media_data = pipeline["create_media"](prompts_data)
    n_media = media_data.get("total", 0)
    log.success(f"Media created: {n_media} pieces")

    if n_media == 0:
        log.error("No media created — check ComfyUI and HuggingFace settings")
        return False

    # ── STEP 5: Write Captions ───────────────────────────────────────
    log.info("\n[5/7] Writing Hinglish captions...")
    captioned_data = pipeline["write_all_captions"](media_data, ideas_data)
    log.success(f"Captions written: {captioned_data.get('total', 0)}")

    # ── STEP 6: Enforce Consistency ──────────────────────────────────
    log.info("\n[6/7] Running consistency check...")
    enforced_data = pipeline["enforce_consistency"](captioned_data)
    approved = enforced_data.get("approved_count", 0)
    log.success(f"Approved for posting: {approved}")

    # ── STEP 7: Schedule Posts ───────────────────────────────────────
    log.info("\n[7/7] Scheduling posts...")
    production_ready = enforced_data.get("production_ready", [])
    scheduled = pipeline["schedule_content"](production_ready)
    log.success(f"Scheduled: {len(scheduled)} posts")

    # ── Post due items ────────────────────────────────────────────────
    log.info("\nChecking for posts due NOW...")
    pipeline["post_due_items"]()

    # ── Summary ──────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).seconds
    log.info("=" * 60)
    log.info("  PIPELINE COMPLETE")
    log.info(f"  Trends scraped: {trends_data.get('total_raw', 0)}")
    log.info(f"  Ideas generated: {ideas_data.get('total_ideas_generated', 0)}")
    log.info(f"  Content produced: {n_media} pieces")
    log.info(f"  Posts scheduled: {len(scheduled)}")
    log.info(f"  Time elapsed: {elapsed}s")
    log.info("=" * 60)

    return True


# ─── Post-Only Mode ───────────────────────────────────────────────────────────
def run_post_only():
    """Just check the queue and post any due items"""
    from pipeline.poster import post_due_items
    from pipeline.scheduler import get_due_posts, get_weekly_calendar

    log.info("Post-only mode: checking queue...")
    due = get_due_posts()
    log.info(f"Posts due: {len(due)}")
    post_due_items()


# ─── Analytics Mode ──────────────────────────────────────────────────────────
def run_analytics_only():
    """Just run analytics"""
    from pipeline.analytics import run_analytics
    result = run_analytics()
    print(json.dumps(result.get("ai_feedback", {}), indent=2, ensure_ascii=False))


# ─── Status Display ───────────────────────────────────────────────────────────
def show_status():
    """Show system status: queue, rate limits, recent posts"""
    from pipeline._7_scheduler import load_queue, get_weekly_calendar
    from utils.storage import load_json

    print("\n" + "=" * 60)
    print("  AANYA SHARMA — SYSTEM STATUS")
    print("=" * 60)

    # Rate limit status
    rates = limiter.status()
    print("\n📊 API Quota Remaining Today:")
    for service, remaining in rates.items():
        bar_filled = int(remaining / max(1, rates.get(service, 100)) * 20)
        print(f"  {service:<15} {remaining:>6} remaining")

    # Queue status
    queue = load_queue()
    scheduled = [q for q in queue if q.get("status") == "scheduled"]
    posted_today = [q for q in queue if q.get("date") == datetime.now().strftime("%Y-%m-%d")
                    and q.get("status") == "posted"]

    print(f"\n📅 Content Queue:")
    print(f"  Scheduled: {len(scheduled)} posts")
    print(f"  Posted today: {len(posted_today)}")

    # Weekly calendar
    print(f"\n🗓️  This Week's Schedule:")
    calendar = get_weekly_calendar()
    for day, posts in sorted(calendar.items()):
        print(f"\n  {day}:")
        for post in posts:
            print(f"    {post['time']} — [{post['platform']}] {post['title'][:40]}")

    # Analytics snapshot
    analytics = load_json("data/analytics/analytics_latest.json")
    if analytics:
        perf = analytics.get("performance_summary", {})
        print(f"\n📈 Latest Analytics:")
        print(f"  Avg engagement: {perf.get('avg_engagement_rate', 0):.2%}")
        print(f"  Best content type: {perf.get('best_content_type', 'N/A')}")
        fb = analytics.get("ai_feedback", {})
        print(f"  Next focus: {fb.get('next_week_focus', 'N/A')}")

    print("\n" + "=" * 60)


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aanya Sharma AI Influencer Orchestrator")
    parser.add_argument("--post-only", action="store_true", help="Only post due items")
    parser.add_argument("--analytics", action="store_true", help="Only run analytics")
    parser.add_argument("--status", action="store_true", help="Show system status")
    args = parser.parse_args()

    if args.post_only:
        run_post_only()
    elif args.analytics:
        run_analytics_only()
    elif args.status:
        show_status()
    else:
        success = run_daily_pipeline()
        sys.exit(0 if success else 1)
