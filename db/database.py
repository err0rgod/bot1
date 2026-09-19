import os 
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, List, Dict
import boto3
from boto3.dynamodb.conditions import Key
import dotenv

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# aws dynamodb resource
REGION = os.getenv("AWS_REGION", "us-east-1")
TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "zerodaily-articles")
MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "https://media.zerodaily.in").rstrip("/")

dynamodb = boto3.resource('dynamodb', region_name = REGION)
articles_table = dynamodb.Table(TABLE_NAME)

def format_iso_date(date_str: Optional[str]) -> str:
    """Converts RFC 2822 / RSS date strings to standard ISO-8601 for chronological sorting."""
    if not date_str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_article_scraped(url : str) -> bool :
    """checks if a article is already scraped or not """
    try:
        response = articles_table.get_item(
            Key={"id": url},
            ProjectionExpression="id"
        )
        return "Item" in response
    except Exception as e:
        logging.warning(f"DynamoDB duplicate check failed for {url} : {e}")
        return False


def save_article(article: Dict, category: str, summary_data: Dict) -> bool :
    try:
        published_at = format_iso_date(article.get("date"))
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        clean_category = category.strip().lower() if category else "default"

        raw_img = article.get("image_url", "")
        # Ensure only valid media.zerodaily.in links or category defaults are persisted
        if raw_img and not raw_img.startswith("https://media.zerodaily.in"):
            logging.warning(f"[DB] Stripping un-optimized 3rd party image URL: {raw_img}")
            final_image_url = f"https://media.zerodaily.in/images/defaults/{clean_category}.webp"
        else:
            final_image_url = raw_img

        item = {
            "id": article["id"],
            "category": category,
            "published_at": published_at,
            "feed_bucket": "ALL",
            "title": article.get("title",""),
            "heading": summary_data.get("roasted_heading", ""),
            "shortSummary": summary_data.get("short_roast_summary", ""),
            "fullSummary": summary_data.get("full_summary", ""),
            "link": article.get("link", article["id"]),
            "image_url": final_image_url,
            "is_breaking": bool(summary_data.get("is_breaking", False)),
            "push_punchline": str(summary_data.get("push_punchline") or ""),
            "created_at": now_iso
        }

        articles_table.put_item(Item=item)
        logging.info(f"[DB] Saved article: {item['heading']}")
        return True
    except Exception as e:
        logging.error(f"[DB ERROR] Failed to save article {article.get('id')} : {e}")
        return False




def get_articles_by_category(category: str, limit: int = 20) -> list[Dict] :
    try:
        response = articles_table.query(
            IndexName = "CategoryIndex",
            KeyConditionExpression=Key("category").eq(category),
            ScanIndexForward=False, #newest first
            Limit = limit
        )

        return response.get("Items", [])
    except Exception as e:
        logging.error(f"[DB ERROR] Failed querying category {category} : {e}")
        return []



def get_latest_feed(limit: int = 20) -> list[Dict] :
    try:
        response = articles_table.query(
            IndexName="GlobalFeedIndex",
            KeyConditionExpression=Key("feed_bucket").eq("ALL"),
            ScanIndexForward=False,
            Limit=limit,
        )

        return response.get("Items", [])
    except Exception as e:
        logging.error(f"[DB ERROR] failed querying global feed: {e}")
        return []