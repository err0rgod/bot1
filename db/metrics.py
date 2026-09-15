import os
import time
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict
import boto3
from boto3.dynamodb.conditions import Key
import dotenv

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REGION = os.getenv("AWS_REGION", "us-east-1")
METRICS_TABLE_NAME = os.getenv("METRICS_TABLE_NAME", "zerodaily-scrape-metrics")
ARTICLES_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "zerodaily-articles")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
metrics_table = dynamodb.Table(METRICS_TABLE_NAME)
articles_table = dynamodb.Table(ARTICLES_TABLE_NAME)


def calculate_gb_seconds(memory_mb: int, duration_seconds: float) -> float:
    """Calculates Lambda GB-seconds compute metric: (Memory MB / 1024) * Duration."""
    memory_gb = memory_mb / 1024.0
    return round(memory_gb * duration_seconds, 4)


def record_scrape_metric(
    category: str,
    duration_seconds: float,
    memory_mb: int = 1024,
    articles_scraped: int = 0,
    articles_summarized: int = 0,
    status: str = "success"
) -> bool:
    """
    Persists scraping execution telemetry to DynamoDB.
    Auto-expires after 30 days via DynamoDB TTL.
    """
    now = datetime.now(timezone.utc)
    metric_date = now.strftime("%Y-%m-%d")
    timestamp_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    metric_id = f"{timestamp_iso}#{category}"
    gb_seconds = calculate_gb_seconds(memory_mb, duration_seconds)
    ttl_epoch = int(time.time()) + (30 * 86400)

    item = {
        "metric_date": metric_date,
        "metric_id": metric_id,
        "timestamp": timestamp_iso,
        "category": category,
        "duration_seconds": Decimal(str(round(duration_seconds, 2))),
        "memory_mb": int(memory_mb),
        "gb_seconds": Decimal(str(gb_seconds)),
        "articles_scraped": int(articles_scraped),
        "articles_summarized": int(articles_summarized),
        "status": status,
        "ttl": ttl_epoch
    }

    try:
        metrics_table.put_item(Item=item)
        logging.info(
            f"[METRICS] Saved scrape metric for {category}: "
            f"duration={duration_seconds:.2f}s, gb_seconds={gb_seconds}, "
            f"scraped={articles_scraped}, summarized={articles_summarized}"
        )
        return True
    except Exception as e:
        logging.error(f"[METRICS ERROR] Failed to record scrape metric: {e}")
        return False


def get_metrics_for_date(date_str: str) -> List[Dict]:
    """Queries all scrape execution metrics for a specific date (YYYY-MM-DD)."""
    try:
        response = metrics_table.query(
            KeyConditionExpression=Key("metric_date").eq(date_str)
        )
        items = response.get("Items", [])
        converted = []
        for item in items:
            cleaned = {}
            for k, v in item.items():
                if isinstance(v, Decimal):
                    cleaned[k] = int(v) if v % 1 == 0 else float(v)
                else:
                    cleaned[k] = v
            converted.append(cleaned)
        return converted
    except Exception as e:
        logging.error(f"[METRICS ERROR] Failed querying metrics for date {date_str}: {e}")
        return []


def get_metrics_for_last_24_hours() -> List[Dict]:
    """Fetches metrics spanning today and yesterday, filtered to the last 24 hours."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    records = []
    records.extend(get_metrics_for_date(yesterday_str))
    records.extend(get_metrics_for_date(today_str))

    # Filter to exact last 24h window
    filtered = [
        item for item in records
        if item.get("timestamp", "") >= cutoff_iso
    ]
    # Sort chronologically
    filtered.sort(key=lambda x: x.get("timestamp", ""))
    return filtered


def get_article_counts_by_category(cutoff_iso: str) -> Dict[str, int]:
    """
    Queries DynamoDB CategoryIndex to count articles stored since cutoff_iso.
    """
    categories = [
        "cybersec",
        "ai",
        "programming",
        "robotics",
        "defense_aerospace",
        "hardware"
    ]
    counts = {}

    for cat in categories:
        try:
            response = articles_table.query(
                IndexName="CategoryIndex",
                KeyConditionExpression=Key("category").eq(cat) & Key("published_at").gte(cutoff_iso),
                Select="COUNT"
            )
            counts[cat] = response.get("Count", 0)
        except Exception as e:
            logging.warning(f"[METRICS] Failed counting articles for category {cat}: {e}")
            counts[cat] = 0

    return counts
