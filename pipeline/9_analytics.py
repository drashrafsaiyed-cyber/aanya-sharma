"""
PIPELINE STEP 9 — Analytics & Feedback Loop
Pulls engagement metrics from Instagram + YouTube.
Feeds performance data back into the content ideator.
Identifies what's working → doubles down. What's not → pivots.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.rate_limiter import get_limiter
from utils.storage import load_json, save_json
from pipeline._llm_utils import llm

log = get_logger("analytics")
limiter = get_limiter()

IG_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
YT_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YT_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

ANALYTICS_DIR = Path("data/analytics")
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

INSIGHTS_FILE = "data/analytics/content_insights.json"
FEEDBACK_FILE = "data/analytics/feedback_for_ideator.json"


# ─── Instagram Insights ───────────────────────────────────────────────────────
def fetch_ig_post_insights(post_id: str) -> Optional[Dict]:
    """Fetch engagement metrics for a specific IG post"""
    if not limiter.acquire("instagram"):
        return None

    import requests

    try:
        # Get post insights
        metrics = "impressions,reach,saved,likes_count,comments_count,shares"
        resp = requests.get(
            f"https://graph.instagram.com/v21.0/{post_id}/insights",
            params={
                "metric": metrics,
                "access_token": IG_ACCESS_TOKEN,
                "period": "lifetime"
            }
        )

        if resp.ok:
            data = resp.json().get("data", [])
            insights = {item["name"]: item["values"][0]["value"] for item in data}
            log.success(f"IG insights fetched for {post_id}")
            return insights
        else:
            log.warning(f"IG insights failed: {resp.status_code}")
            return None

    except Exception as e:
        log.error(f"IG insights error: {e}")
        return None


def fetch_ig_account_insights() -> Optional[Dict]:
    """Fetch overall account insights"""
    if not limiter.acquire("instagram"):
        return None

    import requests

    try:
        # Account-level metrics
        resp = requests.get(
            f"https://graph.instagram.com/v21.0/{IG_ACCOUNT_ID}/insights",
            params={
                "metric": "follower_count,impressions,reach,profile_views",
                "period": "day",
                "access_token": IG_ACCESS_TOKEN
            }
        )

        if resp.ok:
            data = resp.json().get("data", [])
            insights = {}
            for item in data:
                values = item.get("values", [])
                if values:
                    insights[item["name"]] = values[-1]["value"]  # Most recent
            return insights

    except Exception as e:
        log.error(f"Account insights error: {e}")
    return None


def fetch_ig_recent_posts() -> List[Dict]:
    """Fetch recent posts with metrics"""
    if not limiter.acquire("instagram"):
        return []

    import requests

    try:
        # Get recent media
        resp = requests.get(
            f"https://graph.instagram.com/v21.0/{IG_ACCOUNT_ID}/media",
            params={
                "fields": "id,caption,media_type,timestamp,like_count,comments_count",
                "limit": 20,
                "access_token": IG_ACCESS_TOKEN
            }
        )

        posts = []
        if resp.ok:
            items = resp.json().get("data", [])
            for item in items:
                insights = fetch_ig_post_insights(item["id"]) or {}
                posts.append({
                    "id": item["id"],
                    "type": item.get("media_type"),
                    "timestamp": item.get("timestamp"),
                    "caption_preview": (item.get("caption", "") or "")[:100],
                    "likes": item.get("like_count", 0),
                    "comments": item.get("comments_count", 0),
                    "reach": insights.get("reach", 0),
                    "saves": insights.get("saved", 0),
                    "impressions": insights.get("impressions", 0),
                    "engagement_rate": _calc_engagement(
                        item.get("like_count", 0),
                        item.get("comments_count", 0),
                        insights.get("saved", 0),
                        insights.get("reach", 1)
                    )
                })

        log.success(f"Fetched {len(posts)} recent IG posts")
        return posts

    except Exception as e:
        log.error(f"Recent posts fetch failed: {e}")
        return []


# ─── YouTube Analytics ────────────────────────────────────────────────────────
def fetch_youtube_analytics() -> List[Dict]:
    """Fetch recent video performance from YouTube"""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        import pickle

        creds_pickle = "data/youtube_creds.pickle"
        if not Path(creds_pickle).exists():
            log.warning("YouTube not authenticated — skipping analytics")
            return []

        with open(creds_pickle, "rb") as f:
            creds = pickle.load(f)

        if not limiter.acquire("youtube", units=5):
            return []

        yt = build("youtube", "v3", credentials=creds)
        analytics = build("youtubeAnalytics", "v2", credentials=creds)

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        response = analytics.reports().query(
            ids=f"channel=={YT_CHANNEL_ID}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,likes,comments,estimatedMinutesWatched,subscribersGained",
            dimensions="video",
            sort="-views",
            maxResults=20
        ).execute()

        videos = []
        for row in response.get("rows", []):
            vid_id, views, likes, comments, watch_time, subs = row
            videos.append({
                "video_id": vid_id,
                "views": int(views),
                "likes": int(likes),
                "comments": int(comments),
                "watch_time_min": float(watch_time),
                "new_subscribers": int(subs),
                "url": f"https://youtube.com/shorts/{vid_id}"
            })

        log.success(f"YouTube analytics: {len(videos)} videos")
        return videos

    except Exception as e:
        log.warning(f"YouTube analytics unavailable: {e}")
        return []


# ─── Engagement Calculator ────────────────────────────────────────────────────
def _calc_engagement(likes: int, comments: int, saves: int, reach: int) -> float:
    if reach == 0:
        return 0.0
    return round((likes + comments * 2 + saves * 3) / reach, 4)


# ─── Performance Analyzer ────────────────────────────────────────────────────
def analyze_performance(ig_posts: List[Dict], yt_videos: List[Dict]) -> Dict:
    """
    Analyze what content is performing best.
    Returns insights for content ideator.
    """
    if not ig_posts and not yt_videos:
        return {}

    # Sort by engagement
    top_ig = sorted(ig_posts, key=lambda x: x.get("engagement_rate", 0), reverse=True)[:5]
    worst_ig = sorted(ig_posts, key=lambda x: x.get("engagement_rate", 0))[:3]
    top_yt = sorted(yt_videos, key=lambda x: x.get("views", 0), reverse=True)[:3]

    # Find patterns in top performers
    top_captions = [p.get("caption_preview", "") for p in top_ig]
    top_types = [p.get("type", "") for p in top_ig]

    return {
        "top_instagram_posts": top_ig,
        "worst_instagram_posts": worst_ig,
        "top_youtube_videos": top_yt,
        "avg_engagement_rate": sum(p.get("engagement_rate", 0) for p in ig_posts) / max(len(ig_posts), 1),
        "best_content_type": max(set(top_types), key=top_types.count) if top_types else "FEED",
        "top_caption_previews": top_captions,
        "total_posts_analyzed": len(ig_posts) + len(yt_videos)
    }


# ─── AI Feedback Generator ───────────────────────────────────────────────────
def generate_content_feedback(performance: Dict) -> Dict:
    """
    Use LLM to analyze performance data and generate content strategy insights.
    This feeds back into the content ideator for smarter ideas.
    """
    if not performance:
        return {}

    log.info("Generating AI feedback from performance data...")

    top_captions = "\n".join(performance.get("top_caption_previews", [])[:3])
    avg_eng = performance.get("avg_engagement_rate", 0)
    best_type = performance.get("best_content_type", "FEED")

    prompt = f"""You are analyzing performance data for AANYA SHARMA, an Indian motivational influencer.

PERFORMANCE SUMMARY:
- Average engagement rate: {avg_eng:.2%}
- Best performing content type: {best_type}
- Top performing caption samples:
{top_captions or "No data yet"}

Based on this data, provide strategic content recommendations.
Return JSON:
{{
  "what_is_working": ["3-4 specific content strategies performing well"],
  "what_to_avoid": ["2-3 content types/strategies underperforming"],
  "increase_frequency": ["content formats to produce more of"],
  "try_next": ["2-3 new content angles to experiment with"],
  "optimal_content_types": ["ranked list of post types"],
  "tone_adjustments": "any voice/tone recommendations",
  "next_week_focus": "one key content theme to focus on next week for Indian audience"
}}"""

    raw = llm(prompt)
    if raw:
        try:
            from pipeline._llm_utils import parse_json_response
            return parse_json_response(raw)
        except:
            pass

    return {
        "what_is_working": ["Hinglish emotional content", "Morning motivation posts"],
        "what_to_avoid": ["Fully English posts", "Generic motivation"],
        "try_next": ["Indian festival tie-ins", "Relatable struggle stories"],
        "next_week_focus": "Career pressure & family expectations for Indian youth"
    }


# ─── Main ────────────────────────────────────────────────────────────────────
def run_analytics() -> Dict:
    """Full analytics pipeline"""
    log.info("=" * 50)
    log.info("STEP 9: Analytics & Feedback Starting")
    log.info("=" * 50)

    # Fetch data
    ig_posts = fetch_ig_recent_posts()
    yt_videos = fetch_youtube_analytics()

    # Analyze
    performance = analyze_performance(ig_posts, yt_videos)

    # Generate AI feedback
    feedback = generate_content_feedback(performance)

    result = {
        "analyzed_at": datetime.now().isoformat(),
        "instagram_posts": len(ig_posts),
        "youtube_videos": len(yt_videos),
        "performance_summary": performance,
        "ai_feedback": feedback,
        "next_run": (datetime.now() + timedelta(hours=24)).isoformat()
    }

    save_json(result, "analytics_latest.json", "data/analytics")
    save_json({"feedback": feedback, "updated_at": datetime.now().isoformat()},
              "feedback_for_ideator.json", "data/analytics")

    log.success("Analytics complete. Feedback saved for next content cycle.")

    # Log key metric
    avg = performance.get("avg_engagement_rate", 0)
    log.info(f"Average engagement rate: {avg:.2%}")

    return result


def get_ideator_feedback() -> Dict:
    """Load latest feedback for content ideator"""
    return load_json(FEEDBACK_FILE).get("feedback", {})


if __name__ == "__main__":
    result = run_analytics()
    print(json.dumps(result.get("ai_feedback", {}), indent=2, ensure_ascii=False))
