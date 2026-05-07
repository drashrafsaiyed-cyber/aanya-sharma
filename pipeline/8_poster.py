"""
PIPELINE STEP 8 — Auto Poster
Instagram Graph API + YouTube Data API v3
Handles images, reels, carousels, shorts, stories.
All FREE official APIs.
"""
import os
import json
import time
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

from utils.logger import get_logger
from utils.rate_limiter import get_limiter
from utils.storage import load_json, save_json

log = get_logger("poster")
limiter = get_limiter()

# Instagram Graph API
IG_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
IG_API_BASE = "https://graph.instagram.com/v21.0"

# YouTube Data API
YT_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YT_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")
YT_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")

HISTORY_FILE = "data/analytics/post_history.json"


# ════════════════════════════════════════════════════════
#  INSTAGRAM POSTING
# ════════════════════════════════════════════════════════

def _ig_request(method: str, endpoint: str, **kwargs) -> Optional[Dict]:
    """Make Instagram Graph API request with error handling"""
    import requests
    url = f"{IG_API_BASE}/{endpoint}"
    params = kwargs.pop("params", {})
    params["access_token"] = IG_ACCESS_TOKEN

    try:
        if method == "GET":
            resp = requests.get(url, params=params, **kwargs)
        else:
            resp = requests.post(url, params=params, **kwargs)

        if resp.ok:
            return resp.json()
        else:
            log.error(f"Instagram API {endpoint}: {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as e:
        log.error(f"Instagram request failed: {e}")
        return None


def upload_image_to_ig(image_path: str, caption: str,
                        is_reel: bool = False, video_path: str = None) -> Optional[str]:
    """
    Upload image or reel to Instagram.
    Step 1: Create media container
    Step 2: Publish container
    Returns: post_id or None
    """
    if not limiter.acquire("instagram"):
        log.error("Instagram daily limit reached")
        return None

    if not IG_ACCESS_TOKEN or not IG_ACCOUNT_ID:
        log.error("Instagram credentials not configured")
        return None

    import requests

    # Step 1: Create container
    log.info(f"Creating Instagram media container...")

    if is_reel and video_path:
        # For reels: need publicly accessible URL
        # In production: upload to CDN/Drive first, get public URL
        # Here: use Google Drive link if available
        log.warning("Reel posting requires public video URL — use Google Drive public link")
        container_params = {
            "media_type": "REELS",
            "video_url": video_path,  # must be public URL
            "caption": caption[:2200],
            "share_to_feed": "true"
        }
    else:
        container_params = {
            "image_url": image_path,   # must be public URL
            "caption": caption[:2200]
        }

    result = _ig_request("POST", f"{IG_ACCOUNT_ID}/media", json=container_params)
    if not result or "id" not in result:
        log.error(f"Container creation failed: {result}")
        return None

    container_id = result["id"]
    log.info(f"Container created: {container_id}")

    # For video: wait for processing
    if is_reel:
        log.info("Waiting for video processing...")
        for _ in range(30):
            time.sleep(5)
            status = _ig_request("GET", container_id, params={"fields": "status_code"})
            if status and status.get("status_code") == "FINISHED":
                break
            elif status and status.get("status_code") == "ERROR":
                log.error("Video processing failed")
                return None

    # Step 2: Publish container
    log.info("Publishing to Instagram...")
    pub_result = _ig_request("POST", f"{IG_ACCOUNT_ID}/media_publish",
                              json={"creation_id": container_id})

    if pub_result and "id" in pub_result:
        post_id = pub_result["id"]
        log.success(f"Instagram post published: {post_id}")
        return post_id
    else:
        log.error(f"Publish failed: {pub_result}")
        return None


def post_carousel_to_ig(image_paths: List[str], caption: str) -> Optional[str]:
    """Post a carousel (multi-image) to Instagram"""
    if not limiter.acquire("instagram"):
        return None

    if not IG_ACCESS_TOKEN or not IG_ACCOUNT_ID:
        log.error("Instagram credentials not configured")
        return None

    log.info(f"Creating carousel with {len(image_paths)} images...")

    # Step 1: Create container for each image
    children_ids = []
    for img_url in image_paths[:10]:  # max 10 slides
        result = _ig_request("POST", f"{IG_ACCOUNT_ID}/media",
                             json={"image_url": img_url, "is_carousel_item": "true"})
        if result and "id" in result:
            children_ids.append(result["id"])
            time.sleep(1)

    if not children_ids:
        log.error("No carousel children created")
        return None

    # Step 2: Create carousel container
    carousel_result = _ig_request(
        "POST", f"{IG_ACCOUNT_ID}/media",
        json={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption[:2200]
        }
    )

    if not carousel_result or "id" not in carousel_result:
        return None

    # Step 3: Publish
    pub = _ig_request("POST", f"{IG_ACCOUNT_ID}/media_publish",
                      json={"creation_id": carousel_result["id"]})

    if pub and "id" in pub:
        log.success(f"Carousel published: {pub['id']}")
        return pub["id"]
    return None


def post_story_to_ig(image_url: str) -> Optional[str]:
    """Post to Instagram Stories"""
    if not limiter.acquire("instagram"):
        return None

    result = _ig_request("POST", f"{IG_ACCOUNT_ID}/media",
                         json={"image_url": image_url, "media_type": "STORIES"})
    if result and "id" in result:
        pub = _ig_request("POST", f"{IG_ACCOUNT_ID}/media_publish",
                          json={"creation_id": result["id"]})
        if pub and "id" in pub:
            log.success(f"Story published: {pub['id']}")
            return pub["id"]
    return None


# ════════════════════════════════════════════════════════
#  YOUTUBE POSTING
# ════════════════════════════════════════════════════════

def _get_youtube_service():
    """Build authenticated YouTube service"""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        creds_pickle = "data/youtube_creds.pickle"

        creds = None
        if Path(creds_pickle).exists():
            with open(creds_pickle, "rb") as f:
                import pickle
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(YT_CLIENT_SECRET).exists():
                    log.error(f"YouTube client secret not found: {YT_CLIENT_SECRET}")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(YT_CLIENT_SECRET, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(creds_pickle, "wb") as f:
                import pickle
                pickle.dump(creds, f)

        return build("youtube", "v3", credentials=creds)

    except Exception as e:
        log.error(f"YouTube service init failed: {e}")
        return None


def upload_to_youtube(video_path: str, title: str, description: str,
                       tags: List[str] = None, is_short: bool = True) -> Optional[str]:
    """Upload video to YouTube"""
    if not limiter.acquire("youtube", units=1600):  # upload costs 1600 units
        log.error("YouTube quota exceeded")
        return None

    if not Path(video_path).exists():
        log.error(f"Video file not found: {video_path}")
        return None

    service = _get_youtube_service()
    if not service:
        log.warning("YouTube service unavailable — video saved locally")
        return None

    try:
        from googleapiclient.http import MediaFileUpload

        # Add #Shorts to title for YouTube Shorts
        if is_short and "#Shorts" not in title:
            title = f"{title} #Shorts"

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": (tags or []) + (["#Shorts", "AanyaSharma", "motivation", "india"] if is_short else []),
                "categoryId": "26",  # How-to & Style
                "defaultLanguage": "hi",
                "defaultAudioLanguage": "hi"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024  # 1MB chunks
        )

        request = service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        log.info("Uploading to YouTube...")
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response["id"]
        log.success(f"YouTube video uploaded: https://youtube.com/shorts/{video_id}")
        return video_id

    except Exception as e:
        log.error(f"YouTube upload failed: {e}")
        return None


def upload_youtube_thumbnail(video_id: str, thumbnail_path: str):
    """Set custom thumbnail for YouTube video"""
    service = _get_youtube_service()
    if not service or not Path(thumbnail_path).exists():
        return

    try:
        from googleapiclient.http import MediaFileUpload
        service.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path)
        ).execute()
        log.success(f"Thumbnail set for video {video_id}")
    except Exception as e:
        log.warning(f"Thumbnail upload failed: {e}")


# ════════════════════════════════════════════════════════
#  MAIN POSTER
# ════════════════════════════════════════════════════════

def record_post(post_data: Dict):
    """Save post to history"""
    history = load_json(HISTORY_FILE).get("history", [])
    history.append({
        **post_data,
        "posted_at": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    save_json({"history": history}, "post_history.json", "data/analytics")


def mark_queue_posted(post_id: str, platform_post_id: str):
    """Update queue item status"""
    from pipeline.scheduler import load_queue, save_queue
    queue = load_queue()
    for item in queue:
        if item.get("id") == post_id:
            item["status"] = "posted"
            item["platform_post_id"] = platform_post_id
            item["posted_at"] = datetime.now().isoformat()
    save_queue(queue)


def post_item(queue_item: Dict) -> bool:
    """Post a single queued item to its platform"""
    platform = queue_item.get("platform", "instagram_feed")
    media = queue_item.get("media", {})
    caption_data = queue_item.get("caption", {})
    full_caption = caption_data.get("full_caption", "")
    title = queue_item.get("idea_title", "Aanya Sharma")
    post_id_internal = queue_item.get("id", "")

    log.info(f"Posting: {title[:50]} → {platform}")

    platform_post_id = None

    if platform == "instagram_feed":
        image_url = media.get("image")
        if image_url:
            platform_post_id = upload_image_to_ig(image_url, full_caption)

    elif platform == "instagram_reel":
        video_url = media.get("video")
        thumb_url = media.get("thumbnail")
        if video_url:
            platform_post_id = upload_image_to_ig(
                thumb_url or "", full_caption,
                is_reel=True, video_path=video_url
            )

    elif platform == "instagram_carousel":
        slides = media.get("carousel_slides", [])
        if slides:
            platform_post_id = post_carousel_to_ig(slides, full_caption)

    elif platform == "instagram_story":
        image_url = media.get("image")
        if image_url:
            platform_post_id = post_story_to_ig(image_url)

    elif platform == "youtube_short":
        video_path = media.get("video")
        thumb_path = media.get("thumbnail")
        yt_title = caption_data.get("youtube_title", title)
        tags_from_hashtags = [
            h.replace("#", "")
            for h in caption_data.get("hashtags", "").split()
            if h.startswith("#")
        ][:15]

        if video_path:
            platform_post_id = upload_to_youtube(
                video_path, yt_title, full_caption,
                tags=tags_from_hashtags, is_short=True
            )
            if platform_post_id and thumb_path:
                upload_youtube_thumbnail(platform_post_id, thumb_path)

    if platform_post_id:
        record_post({
            "internal_id": post_id_internal,
            "platform": platform,
            "platform_post_id": platform_post_id,
            "title": title,
            "caption_preview": full_caption[:100]
        })
        mark_queue_posted(post_id_internal, platform_post_id)
        log.success(f"Posted successfully: {platform_post_id}")
        return True
    else:
        log.error(f"Posting failed for: {title[:50]}")
        return False


def post_due_items():
    """Check queue and post any items that are due"""
    from pipeline.scheduler import get_due_posts

    due = get_due_posts()
    if not due:
        log.info("No posts due right now")
        return

    log.info(f"Found {len(due)} posts due for publishing")
    for item in due:
        success = post_item(item)
        if not success:
            log.warning(f"Will retry: {item.get('idea_title', 'Unknown')}")


if __name__ == "__main__":
    log.info("Poster — checking for due posts...")
    post_due_items()
