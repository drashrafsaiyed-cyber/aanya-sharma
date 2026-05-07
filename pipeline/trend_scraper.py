"""
PIPELINE STEP 1 — Trend Scraper
Sources: Google Trends (pytrends) + Reddit + YouTube Trending
Target: Indian audience, Motivational/Mindset niche
All FREE — no paid APIs
"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.rate_limiter import get_limiter
from utils.storage import save_json

log = get_logger("trend_scraper")
limiter = get_limiter()


# ─── Seed topics relevant to Aanya's niche ─────────────────────────────────
SEED_TOPICS = [
    "motivation hindi",
    "mindset success India",
    "self improvement",
    "morning routine india",
    "log kya kahenge",
    "confidence girl india",
    "study motivation india",
    "self love india",
    "success tips hindi",
    "Indian girl inspiration"
]

INDIAN_SUBREDDITS = [
    "india", "IndianGirlsOnReddit", "developersIndia",
    "indian", "motivation", "selfimprovement"
]


# ─── Google Trends ──────────────────────────────────────────────────────────
def scrape_google_trends() -> List[Dict]:
    """Pull trending topics from Google Trends for India"""
    log.info("Scraping Google Trends (India)...")
    trends = []

    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="hi-IN", tz=-330)  # IST

        # Trending searches right now in India
        try:
            realtime = pytrends.trending_searches(pn="india")
            for _, row in realtime.iterrows():
                trends.append({
                    "topic": str(row[0]),
                    "source": "google_trends_realtime",
                    "score": 100,
                    "region": "India"
                })
            log.success(f"Google realtime trends: {len(trends)} topics")
        except Exception as e:
            log.warning(f"Realtime trends failed: {e}")

        # Related topics for our seed keywords
        for seed in SEED_TOPICS[:3]:  # limit to avoid rate limiting
            try:
                pytrends.build_payload([seed], geo="IN", timeframe="now 7-d")
                related = pytrends.related_topics()
                if seed in related and related[seed]["top"] is not None:
                    for _, row in related[seed]["top"].head(5).iterrows():
                        trends.append({
                            "topic": row["topic_title"],
                            "source": "google_trends_related",
                            "score": int(row["value"]),
                            "seed": seed,
                            "region": "India"
                        })
                time.sleep(2)  # be gentle with pytrends
            except Exception as e:
                log.warning(f"Related topics for '{seed}': {e}")

    except ImportError:
        log.warning("pytrends not installed. pip install pytrends")
    except Exception as e:
        log.error(f"Google Trends scraping failed: {e}")

    return trends


# ─── Reddit ─────────────────────────────────────────────────────────────────
def scrape_reddit() -> List[Dict]:
    """Pull hot posts from Indian subreddits"""
    log.info("Scraping Reddit for Indian trends...")
    posts = []

    reddit_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if not reddit_id or not reddit_secret:
        log.warning("Reddit credentials not set — skipping Reddit scrape")
        return posts

    try:
        import praw

        reddit = praw.Reddit(
            client_id=reddit_id,
            client_secret=reddit_secret,
            user_agent=os.getenv("REDDIT_USER_AGENT", "AanyaBot/1.0")
        )

        for sub_name in INDIAN_SUBREDDITS:
            if not limiter.acquire("reddit"):
                break
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=5):
                    if post.score > 50:
                        posts.append({
                            "topic": post.title,
                            "source": f"reddit_r/{sub_name}",
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "comments": post.num_comments,
                            "url": f"https://reddit.com{post.permalink}"
                        })
            except Exception as e:
                log.warning(f"Reddit r/{sub_name}: {e}")

        log.success(f"Reddit posts collected: {len(posts)}")

    except ImportError:
        log.warning("praw not installed. pip install praw")
    except Exception as e:
        log.error(f"Reddit scraping failed: {e}")

    return posts


# ─── YouTube Trending ────────────────────────────────────────────────────────
def scrape_youtube_trending() -> List[Dict]:
    """Pull trending YouTube videos in India"""
    log.info("Scraping YouTube trending (India)...")
    videos = []

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        log.warning("YOUTUBE_API_KEY not set — skipping YouTube trending")
        return videos

    if not limiter.acquire("youtube", units=1):
        log.error("YouTube daily quota exceeded")
        return videos

    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", developerKey=api_key)

        # Trending videos in India (regionCode=IN)
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="IN",
            videoCategoryId="22",  # People & Blogs
            maxResults=20
        )
        response = request.execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            videos.append({
                "topic": snippet["title"],
                "channel": snippet["channelTitle"],
                "source": "youtube_trending",
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "tags": snippet.get("tags", [])[:5],
                "video_id": item["id"]
            })

        # Also check Education category
        request2 = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="IN",
            videoCategoryId="27",  # Education
            maxResults=10
        )
        response2 = request2.execute()
        for item in response2.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            videos.append({
                "topic": snippet["title"],
                "channel": snippet["channelTitle"],
                "source": "youtube_trending_education",
                "views": int(stats.get("viewCount", 0)),
                "tags": snippet.get("tags", [])[:5],
                "video_id": item["id"]
            })

        log.success(f"YouTube trending videos: {len(videos)}")

    except ImportError:
        log.warning("google-api-python-client not installed")
    except Exception as e:
        log.error(f"YouTube trending failed: {e}")

    return videos


# ─── Trend Ranker ───────────────────────────────────────────────────────────
def rank_trends(google: List, reddit: List, youtube: List) -> List[Dict]:
    """
    Merge and rank all trends by relevance to Aanya's niche.
    Scores: virality + alignment with motivational/mindset content.
    """
    MOTIVATION_KEYWORDS = [
        "motivation", "mindset", "success", "confidence", "girl", "study",
        "career", "love", "life", "happiness", "anxiety", "stress", "hustle",
        "morning", "habit", "routine", "inspire", "dream", "goal", "achieve",
        "padhna", "naukri", "exam", "result", "future", "khud", "aage",
        "self", "grow", "improve", "change", "positiv", "power", "strong"
    ]

    all_trends = []

    for item in google:
        topic = item.get("topic", "").lower()
        niche_score = sum(1 for k in MOTIVATION_KEYWORDS if k in topic) * 20
        all_trends.append({**item, "relevance_score": item.get("score", 50) + niche_score})

    for item in reddit:
        topic = item.get("topic", "").lower()
        niche_score = sum(1 for k in MOTIVATION_KEYWORDS if k in topic) * 20
        virality = min(100, item.get("score", 0) / 10)
        all_trends.append({**item, "relevance_score": virality + niche_score})

    for item in youtube:
        topic = item.get("topic", "").lower()
        niche_score = sum(1 for k in MOTIVATION_KEYWORDS if k in topic) * 20
        virality = min(100, item.get("views", 0) / 100000)
        all_trends.append({**item, "relevance_score": virality + niche_score})

    # Sort by relevance
    all_trends.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return all_trends[:20]  # top 20


# ─── Main ────────────────────────────────────────────────────────────────────
def scrape_trends() -> Dict:
    """Run full trend scrape pipeline"""
    log.info("=" * 50)
    log.info("STEP 1: Trend Scraper Starting")
    log.info("=" * 50)

    google_trends = scrape_google_trends()
    reddit_trends = scrape_reddit()
    youtube_trends = scrape_youtube_trending()

    ranked = rank_trends(google_trends, reddit_trends, youtube_trends)

    result = {
        "scraped_at": datetime.now().isoformat(),
        "total_raw": len(google_trends) + len(reddit_trends) + len(youtube_trends),
        "top_trends": ranked,
        "sources": {
            "google_trends": len(google_trends),
            "reddit": len(reddit_trends),
            "youtube": len(youtube_trends)
        }
    }

    # Save for next pipeline step
    save_json(result, f"trends_{datetime.now().strftime('%Y%m%d')}.json", "data/trends")
    log.success(f"Trend scrape complete. Top trend: {ranked[0]['topic'] if ranked else 'N/A'}")

    return result


if __name__ == "__main__":
    result = scrape_trends()
    print(json.dumps(result, indent=2, ensure_ascii=False))
