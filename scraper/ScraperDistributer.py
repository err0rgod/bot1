import json
import logging
import os
from datetime import datetime, timezone
from scraper.Feeds import NewsFeeds           # Import your class!
from scraper.Scraper import scrape_rss_feed   # Import your engine!
    
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
def lambda_handler(event, context):
    target_category = event.get("category", "cybersec")
        
    # 1. Get the URLs from feeds.py
    feeds = NewsFeeds.get_feeds(target_category)
    if not feeds:
        return {"statusCode": 400, "body": "Category not found"}
    
    # 2. Tell scraper.py to do the heavy lifting
    news = scrape_rss_feed(target_category, feeds)
        
    # 3. Save the results
    today = datetime.now(timezone.utc).date()
    tmp_dir = os.environ.get("TMP_DIR")
    if not tmp_dir:
        tmp_dir = "/tmp" if os.name != "nt" else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    filename = os.path.join(tmp_dir, f"scraped_{target_category}_{today}.json")
        
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(news, f, indent=4)
            
    return {"statusCode": 200, "body": f"Successfully scraped {target_category}", "count": len(news)}
    



    
# For Local Testing
if __name__ == "__main__":
    lambda_handler({"category": "ai"}, None)
    logging.info("Scraped AI")
    lambda_handler({"category": "cybersec"}, None)
    logging.info("Scraped CYBERSEC")
    lambda_handler({"category": "programming"}, None)
    logging.info("Scraped PROGRAMMING")
    lambda_handler({"category": "robotics"}, None)
    logging.info("Scraped ROBOTICS")
    lambda_handler({"category": "defence_aerospace"}, None)
    logging.info("Scraped DEFENSE/AEROSPACE")
    lambda_handler({"category": "hardware"}, None)
    logging.info("Scraped HARDWARE")