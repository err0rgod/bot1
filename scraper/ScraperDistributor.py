# lambda_scrape_handler.py
import json
import logging
from datetime import datetime, timezone
from Feeds import NewsFeeds           # Import your class!
from Scraper import scrape_rss_feed   # Import your engine!
    
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
    filename = f"D:/bot1/tmp/scraped_{target_category}_{today}.json" 
        
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(news, f, indent=4)
            
    return {"statusCode": 200, "body": f"Successfully scraped {target_category}"}
    
    
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