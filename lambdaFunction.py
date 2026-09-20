import os
import json
import time
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from scraper.Feeds import NewsFeeds
from scraper.Scraper import scrape_rss_feed
from llm.SummariserDistributer import process_single_article
from scraper.ScraperDistributer import lambda_handler as scrape_handler
from llm.SummariserDistributer import lambdaHandler as summarize_handler
from db.metrics import record_scrape_metric, calculate_gb_seconds
from notifications.reporter import send_morning_digest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# All supported news categories
ALL_CATEGORIES = [
    "cybersec",
    "ai",
    "programming",
    "robotics",
    "defense_aerospace",
    "hardware",
    "finance"
]


def run_pipeline_for_category(category: str, context=None) -> dict:
    """
    Executes the full end-to-end pipeline for a single category:
      1. Loads RSS feed URLs for the category.
      2. Scrapes, filters today's news, and performs LLM semantic deduplication.
      3. Scrapes full article content & extracts top images.
      4. Concurrently processes articles with LLM (roast heading, short summary, full summary).
      5. Automatically saves each summarized article into DynamoDB.
      6. Writes local JSON backups into /tmp/ for debugging / audit logs.
      7. Persists execution telemetry (time, GB-seconds, article counts) into DynamoDB.
    """
    logging.info(f"=== Starting pipeline for category: {category} ===")
    start_time = time.time()
    memory_mb = int(getattr(context, "memory_limit_in_mb", 1024)) if context else 1024

    # 1. Fetch configured feeds for this category
    feeds = NewsFeeds.get_feeds(category)
    if not feeds:
        logging.warning(f"No feeds configured for category: {category}")
        duration_seconds = round(time.time() - start_time, 2)
        gb_seconds = calculate_gb_seconds(memory_mb, duration_seconds)
        record_scrape_metric(category, duration_seconds, memory_mb, 0, 0, status="no_feeds")
        return {
            "category": category,
            "scraped": 0,
            "summarized": 0,
            "status": "no_feeds",
            "duration_seconds": duration_seconds,
            "gb_seconds": gb_seconds
        }

    # 2. Scrape RSS feeds + LLM semantic deduplication + article text extraction
    scraped_articles = scrape_rss_feed(category, feeds)
    logging.info(f"Scraped {len(scraped_articles)} unique articles for {category}")

    if not scraped_articles:
        duration_seconds = round(time.time() - start_time, 2)
        gb_seconds = calculate_gb_seconds(memory_mb, duration_seconds)
        record_scrape_metric(category, duration_seconds, memory_mb, 0, 0, status="no_new_articles")
        return {
            "category": category,
            "scraped": 0,
            "summarized": 0,
            "status": "no_new_articles",
            "duration_seconds": duration_seconds,
            "gb_seconds": gb_seconds
        }

    # 3. Save scraped backup to /tmp (cross-platform path resolution)
    today = datetime.now(timezone.utc).date()
    tmp_dir = os.environ.get("TMP_DIR")
    if not tmp_dir:
        tmp_dir = "/tmp" if os.name != "nt" else os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    scraped_backup_file = os.path.join(tmp_dir, f"scraped_{category}_{today}.json")
    try:
        with open(scraped_backup_file, "w", encoding="utf-8") as f:
            json.dump(scraped_articles, f, indent=4)
    except Exception as e:
        logging.warning(f"Could not write scraped backup to {scraped_backup_file}: {e}")

    # 4. Parallel summarization & DynamoDB storage via ThreadPoolExecutor (max 5 threads)
    final_data = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_article = {
            executor.submit(process_single_article, art, category): art
            for art in scraped_articles
        }
        for future in as_completed(future_to_article):
            res = future.result()
            if res:
                final_data.append(res)

    logging.info(f"Successfully processed {len(final_data)}/{len(scraped_articles)} articles for {category}")

    # 5. Save final summary backup to /tmp
    final_backup_file = os.path.join(tmp_dir, f"final_{category}_{today}.json")
    try:
        with open(final_backup_file, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=4)
    except Exception as e:
        logging.warning(f"Could not write final backup to {final_backup_file}: {e}")

    duration_seconds = round(time.time() - start_time, 2)
    gb_seconds = calculate_gb_seconds(memory_mb, duration_seconds)

    # 6. Record execution telemetry
    record_scrape_metric(
        category=category,
        duration_seconds=duration_seconds,
        memory_mb=memory_mb,
        articles_scraped=len(scraped_articles),
        articles_summarized=len(final_data),
        status="success"
    )

    return {
        "category": category,
        "scraped": len(scraped_articles),
        "summarized": len(final_data),
        "status": "success",
        "duration_seconds": duration_seconds,
        "gb_seconds": gb_seconds
    }


def lambda_handler(event, context):
    """
    Unified AWS Lambda entry point.

    Supported event structures:
      1. Single category pipeline (EventBridge schedule):
         {"category": "ai"}
      2. Full pipeline across all categories:
         {"category": "all"} or {}
      3. Scraper-only action:
         {"action": "scrape", "category": "ai"}
      4. Summarizer-only action:
         {"action": "summarize", "category": "ai"}
    """
    if not isinstance(event, dict):
        event = {}

    logging.info(f"Received Lambda event: {json.dumps(event)}")
    action = event.get("action", "pipeline")
    category = event.get("category")

    # Modular sub-actions
    if action == "scrape":
        return scrape_handler(event, context)
    elif action == "summarize":
        return summarize_handler(event, context)
    elif action in ("daily_report", "morning_report", "send_digest"):
        recipient = event.get("recipient")
        digest_result = send_morning_digest(recipient=recipient)
        status_code = 200 if digest_result.get("sent") or digest_result.get("status") == "skipped" else 500
        return {
            "statusCode": status_code,
            "body": json.dumps({
                "message": "Daily report processed",
                "result": digest_result
            }, default=str)
        }

    # Full end-to-end pipeline (default)
    if category and category != "all":
        results = [run_pipeline_for_category(category, context=context)]
    else:
        results = [run_pipeline_for_category(cat, context=context) for cat in ALL_CATEGORIES]

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Pipeline execution completed",
            "results": results
        }, default=str)
    }


if __name__ == "__main__":
    lambda_handler({"category": "ai"}, None)
